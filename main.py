# RUG WORLD CUP 26 — backend de transmision en vivo (torneo autoconclusivo 72hs)
# El motor corre en el server con reloj por TIEMPO (no por compras) y se transmite
# por WebSocket a todos. El estado se persiste en Postgres para sobrevivir reinicios.
# Arranque MANUAL con DEV_KEY (sincronizado con el stream).

import asyncio
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import db
from engine import Tournament

torneo = Tournament()

# DEV_KEY protege los endpoints de control (arrancar / resetear el torneo)
DEV_KEY = os.environ.get("DEV_KEY", "")
SAVE_EVERY = 10        # ademas de guardar en cada partido, guardar cada 10 ticks (~10s)


class Hub:
    def __init__(self):
        self.conns = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)
        await ws.send_text(json.dumps(torneo.snapshot()))
        await ws.send_text(json.dumps(torneo.bracket_state()))
        await ws.send_text(json.dumps(torneo.groups_state()))

    def disconnect(self, ws: WebSocket):
        self.conns.discard(ws)

    async def broadcast(self, msg):
        data = json.dumps(msg)
        muertos = []
        for ws in list(self.conns):
            try:
                await ws.send_text(data)
            except Exception:
                muertos.append(ws)
        for ws in muertos:
            self.conns.discard(ws)


hub = Hub()


async def sim_loop():
    last_version = -1
    n = 0
    while True:
        await asyncio.sleep(1.0)
        torneo.tick()
        await hub.broadcast(torneo.snapshot())
        n += 1
        changed = torneo.version != last_version
        if changed:
            last_version = torneo.version
            await hub.broadcast(torneo.bracket_state())
            await hub.broadcast(torneo.groups_state())
        # persistir: en cada cambio (partido terminado / arranque) y periodicamente
        if torneo.started and (changed or n % SAVE_EVERY == 0):
            try:
                await db.save_state(torneo.to_dict())
            except Exception as ex:
                print("save_state error:", ex)


@asynccontextmanager
async def lifespan(app):
    # persistencia: conectar y RESTAURAR el torneo si habia uno en curso
    try:
        await db.init_pool()
        print("persistencia: Postgres conectada")
        saved = await db.load_state()
        if saved:
            try:
                torneo.from_dict(saved)
                print("torneo RESTAURADO desde Postgres (slot",
                      torneo.cur_slot, "- started", torneo.started, ")")
            except Exception as ex:
                print("no se pudo restaurar el estado guardado:", ex)
    except Exception as ex:
        print("persistencia DESHABILITADA (sin DATABASE_URL valida):", ex)
    tarea = asyncio.create_task(sim_loop())
    yield
    tarea.cancel()
    # guardar al cerrar (best-effort)
    try:
        if torneo.started:
            await db.save_state(torneo.to_dict())
    except Exception:
        pass
    try:
        await db.close_pool()
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _auth(key):
    return bool(DEV_KEY) and key == DEV_KEY


@app.get("/")
async def health():
    s = torneo.snapshot()
    return {
        "ok": True,
        "viewers": len(hub.conns),
        "started": torneo.started,
        "fase": s["fase"],
        "ronda": s["ronda"],
        "partido": str(s["partido"]) + "/" + str(s["partidos_ronda"]),
        "remaining_h": round(s["remaining"] / 3600, 2),
        "campeon": s["campeon"],
        "db": db.enabled(),
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


# ============================== CONTROL DEL TORNEO (protegido) =================
@app.get("/api/control/start")
async def api_start(key: str = "", ago: float = 0.0):
    """Arranca el torneo. 'ago' (segundos) permite arrancar 'como si hubiera empezado
    hace X seg' (util para testear; en el lanzamiento real va en 0)."""
    if not _auth(key):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    ok = torneo.start(seconds_ago=ago)
    if ok:
        try:
            await db.save_state(torneo.to_dict())
        except Exception:
            pass
        await hub.broadcast(torneo.snapshot())
        await hub.broadcast(torneo.bracket_state())
        await hub.broadcast(torneo.groups_state())
    s = torneo.snapshot()
    return {"started": torneo.started, "ya_estaba": (not ok),
            "remaining_h": round(s["remaining"] / 3600, 2)}


@app.get("/api/control/reset")
async def api_reset(key: str = "", confirm: str = ""):
    """Reinicia a un torneo nuevo en pre-partido (sorteo nuevo). Requiere confirm=yes."""
    if not _auth(key):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    if confirm != "yes":
        return JSONResponse({"error": "falta confirm=yes"}, status_code=400)
    torneo.reset()
    try:
        await db.save_state(torneo.to_dict())
    except Exception:
        pass
    await hub.broadcast(torneo.snapshot())
    await hub.broadcast(torneo.bracket_state())
    await hub.broadcast(torneo.groups_state())
    return {"ok": True, "started": torneo.started}


@app.get("/api/control/clear")
async def api_clear(key: str = "", confirm: str = ""):
    """Borra el estado guardado en Postgres (no toca el torneo en memoria). confirm=yes."""
    if not _auth(key):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    if confirm != "yes":
        return JSONResponse({"error": "falta confirm=yes"}, status_code=400)
    ok = await db.clear_state()
    return {"cleared": ok}


# ============================== PAGINA DE DEBUG ================================
TEST_HTML = """<!doctype html><meta charset="utf-8">
<title>RUGWC backend</title>
<body style="font-family:monospace;background:#070b12;color:#cfe3e0;padding:24px;font-size:18px">
<h3 style="color:#ffb02e">RUG WORLD CUP 26 - motor en vivo (72hs)</h3>
<div id="round" style="color:#36e0d0;margin-bottom:10px">conectando...</div>
<div id="match" style="font-size:28px;margin:10px 0"></div>
<div id="extra" style="color:#8aa;margin-top:6px"></div>
<div id="champ" style="color:#ffb02e;font-size:22px;margin-top:14px"></div>
<script>
function hms(s){var h=Math.floor(s/3600),m=Math.floor((s%3600)/60);return h+"h "+m+"m";}
var proto = location.protocol === "https:" ? "wss" : "ws";
var ws = new WebSocket(proto + "://" + location.host + "/ws");
ws.onmessage = function(e){
  var s = JSON.parse(e.data);
  if(s.type !== "state") return;
  if(!s.started){
    document.getElementById("round").textContent = "PRE-PARTIDO - esperando arranque";
  } else {
    document.getElementById("round").textContent =
      "EN VIVO - " + s.ronda + " - Partido " + s.partido + "/" + s.partidos_ronda +
      " - min " + s.minuto + "'" + (s.penales ? " - PENALES" : "");
  }
  document.getElementById("match").innerHTML =
    '<span style="color:' + s.local.color + '">' + s.local.short + '</span> ' +
    s.local.goles + ' - ' + s.visita.goles +
    ' <span style="color:' + s.visita.color + '">' + s.visita.short + '</span>';
  document.getElementById("extra").textContent =
    "energia " + s.energia + " - restante " + hms(s.remaining);
  document.getElementById("champ").textContent = s.campeon ? ("CAMPEON: " + s.campeon) : "";
};
ws.onclose = function(){ document.getElementById("round").textContent = "desconectado"; };
</script>
</body>"""


@app.get("/test", response_class=HTMLResponse)
async def test_page():
    return TEST_HTML
