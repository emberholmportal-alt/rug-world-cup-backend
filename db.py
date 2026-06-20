# db.py — persistencia del estado del torneo en PostgreSQL (asyncpg).
# Una sola fila (id=1) con el estado serializado del torneo en JSON (columna TEXT).
# Si no hay DATABASE_URL, todo queda deshabilitado de forma silenciosa (no rompe).
import os
import ssl
import json

import asyncpg

_pool = None

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS rwc_state (
    id         INTEGER PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def enabled():
    return _pool is not None


async def init_pool():
    global _pool
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL no configurada")
    # Render entrega 'postgres://'; asyncpg quiere 'postgresql://'
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    # La URL EXTERNA de Render trae ?sslmode=require; la INTERNA (misma region) no necesita SSL.
    want_ssl = ("sslmode=require" in dsn) or ("sslmode=verify" in dsn) \
        or (os.environ.get("DB_SSL", "").lower() in ("1", "true", "require"))
    dsn = dsn.split("?")[0]  # asyncpg recibe el SSL por parametro, no por query string
    ssl_arg = None
    if want_ssl:
        ssl_arg = ssl.create_default_context()
        ssl_arg.check_hostname = False
        ssl_arg.verify_mode = ssl.CERT_NONE
    _pool = await asyncpg.create_pool(dsn, ssl=ssl_arg, min_size=1, max_size=3, command_timeout=10)
    async with _pool.acquire() as con:
        await con.execute(CREATE_SQL)


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def save_state(data):
    """Guarda (upsert) el estado del torneo. No-op si no hay pool."""
    if _pool is None:
        return False
    js = json.dumps(data)
    async with _pool.acquire() as con:
        await con.execute(
            "INSERT INTO rwc_state (id, data, updated_at) VALUES (1, $1, now()) "
            "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = now()",
            js,
        )
    return True


async def load_state():
    """Devuelve el dict del estado guardado, o None si no hay nada / no hay pool."""
    if _pool is None:
        return None
    async with _pool.acquire() as con:
        row = await con.fetchval("SELECT data FROM rwc_state WHERE id = 1")
    if not row:
        return None
    try:
        return json.loads(row)
    except (ValueError, TypeError):
        return None


async def clear_state():
    """Borra el estado guardado (para empezar un torneo limpio). No-op si no hay pool."""
    if _pool is None:
        return False
    async with _pool.acquire() as con:
        await con.execute("DELETE FROM rwc_state WHERE id = 1")
    return True
