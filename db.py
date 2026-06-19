# db.py — almacenamiento de comentarios en PostgreSQL (asyncpg)
# Tablas con prefijo rwc_ para poder convivir en la misma Postgres del prode si se quiere.
import os
import ssl
from datetime import timezone

import asyncpg

_pool = None

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS rwc_comments (
    id           BIGSERIAL PRIMARY KEY,
    nick         TEXT NOT NULL,
    body         TEXT NOT NULL,
    parent_id    BIGINT REFERENCES rwc_comments(id) ON DELETE CASCADE,
    author_token TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ,
    deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_rwc_comments_parent  ON rwc_comments(parent_id);
CREATE INDEX IF NOT EXISTS idx_rwc_comments_created ON rwc_comments(created_at);
CREATE TABLE IF NOT EXISTS rwc_comment_likes (
    comment_id BIGINT NOT NULL REFERENCES rwc_comments(id) ON DELETE CASCADE,
    token      TEXT NOT NULL,
    PRIMARY KEY (comment_id, token)
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
    _pool = await asyncpg.create_pool(dsn, ssl=ssl_arg, min_size=1, max_size=5, command_timeout=10)
    async with _pool.acquire() as con:
        await con.execute(CREATE_SQL)


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _iso(dt):
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_comment(r, likes=0):
    deleted = r["deleted"]
    return {
        "id": r["id"],
        "nick": r["nick"],
        "body": "" if deleted else r["body"],
        "parent_id": r["parent_id"],
        "created_at": _iso(r["created_at"]),
        "updated_at": _iso(r["updated_at"]),
        "deleted": deleted,
        "likes": likes,
    }


async def list_comments(limit=200):
    async with _pool.acquire() as con:
        rows = await con.fetch(
            """
            SELECT c.id, c.nick, c.body, c.parent_id, c.created_at, c.updated_at, c.deleted,
                   COALESCE(l.cnt, 0) AS likes
            FROM rwc_comments c
            LEFT JOIN (
                SELECT comment_id, count(*) AS cnt
                FROM rwc_comment_likes GROUP BY comment_id
            ) l ON l.comment_id = c.id
            ORDER BY c.id DESC
            LIMIT $1
            """,
            limit,
        )
    return [_row_to_comment(r, r["likes"]) for r in rows]


async def parent_exists(parent_id):
    if parent_id is None:
        return True
    async with _pool.acquire() as con:
        v = await con.fetchval(
            "SELECT 1 FROM rwc_comments WHERE id=$1 AND deleted=FALSE", parent_id
        )
    return v is not None


async def add_comment(nick, body, parent_id, token):
    async with _pool.acquire() as con:
        r = await con.fetchrow(
            """
            INSERT INTO rwc_comments (nick, body, parent_id, author_token)
            VALUES ($1, $2, $3, $4)
            RETURNING id, nick, body, parent_id, created_at, updated_at, deleted
            """,
            nick, body, parent_id, token,
        )
    return _row_to_comment(r, 0)


async def _count_likes(con, cid):
    n = await con.fetchval(
        "SELECT count(*) FROM rwc_comment_likes WHERE comment_id=$1", cid
    )
    return n or 0


async def edit_comment(cid, body, token):
    async with _pool.acquire() as con:
        r = await con.fetchrow(
            """
            UPDATE rwc_comments SET body=$1, updated_at=now()
            WHERE id=$2 AND author_token=$3 AND deleted=FALSE
            RETURNING id, nick, body, parent_id, created_at, updated_at, deleted
            """,
            body, cid, token,
        )
        if r is None:
            return None
        n = await _count_likes(con, cid)
    return _row_to_comment(r, n)


async def delete_comment(cid, token, admin=False):
    async with _pool.acquire() as con:
        r = await con.fetchrow(
            """
            UPDATE rwc_comments SET deleted=TRUE, body=''
            WHERE id=$1 AND (author_token=$2 OR $3) AND deleted=FALSE
            RETURNING id
            """,
            cid, token, admin,
        )
    return r is not None


async def like_comment(cid, token, on=True):
    async with _pool.acquire() as con:
        if on:
            await con.execute(
                "INSERT INTO rwc_comment_likes (comment_id, token) "
                "VALUES ($1, $2) ON CONFLICT DO NOTHING",
                cid, token,
            )
        else:
            await con.execute(
                "DELETE FROM rwc_comment_likes WHERE comment_id=$1 AND token=$2",
                cid, token,
            )
        return await _count_likes(con, cid)
