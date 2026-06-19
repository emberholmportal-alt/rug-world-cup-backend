# RUG WORLD CUP 26 — backend de transmision en vivo
# Motor real del torneo (48 chains, eliminacion directa) corriendo en el server
# y transmitido por WebSocket a todos. PumpPortal se conecta en el proximo paso.

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import db
from engine import Tournament

torneo = Tournament()


class Hub:
    def __init__(self):
        self.conns = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)
        await ws.send_text(json.dumps(torneo.snapshot()))
        await ws.send_text(json.dumps(torneo.bracket_state()))

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
    while True:
        await asyncio.sleep(1.0)
        torneo.tick()
        await hub.broadcast(torneo.snapshot())
        if torneo.version != last_version:
            last_version = torneo.version
            await hub.broadcast(torneo.bracket_state())


@asynccontextmanager
async def lifespan(app):
    try:
        await db.init_pool()
        print("comentarios: Postgres conectada")
    except Exception as e:
        print("comentarios DESHABILITADOS (sin DATABASE_URL valida):", e)
    tarea = asyncio.create_task(sim_loop())
    yield
    tarea.cancel()
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

# ---- comentarios: config y modelos ----
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
RATE_SECONDS = 20      # 1 comentario cada 20s por token (antispam)
MAX_BODY = 500
MAX_NICK = 24
_last_post = {}        # token -> timestamp, en memoria


class CommentIn(BaseModel):
    nick: str = "anon"
    body: str
    parent_id: Optional[int] = None
    token: str


class EditIn(BaseModel):
    body: str
    token: str


class LikeIn(BaseModel):
    token: str


def _clean_nick(s):
    s = (s or "").strip()
    return (s or "anon")[:MAX_NICK]


def _clean_body(s):
    return (s or "").strip()[:MAX_BODY]


def _prune_rate():
    if len(_last_post) > 8000:
        now = time.time()
        for k in [k for k, t in _last_post.items() if now - t > 60]:
            _last_post.pop(k, None)


@app.get("/")
async def health():
    s = torneo.snapshot()
    return {"ok": True, "viewers": len(hub.conns),
            "ronda": s["ronda"], "partido": str(s["partido"]) + "/" + str(s["partidos_ronda"])}


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


# ============================== COMENTARIOS (REST + broadcast WS) ==============
@app.get("/api/comments")
async def api_list_comments(limit: int = 200):
    if not db.enabled():
        return JSONResponse({"error": "comentarios no configurados"}, status_code=503)
    limit = max(1, min(500, limit))
    return await db.list_comments(limit)


@app.post("/api/comments")
async def api_add_comment(c: CommentIn):
    if not db.enabled():
        return JSONResponse({"error": "comentarios no configurados"}, status_code=503)
    body = _clean_body(c.body)
    if not body:
        return JSONResponse({"error": "vacio"}, status_code=400)
    if not c.token:
        return JSONResponse({"error": "falta token"}, status_code=400)
    now = time.time()
    last = _last_post.get(c.token, 0)
    if now - last < RATE_SECONDS:
        return JSONResponse(
            {"error": "muy rapido", "retry": int(RATE_SECONDS - (now - last)) + 1},
            status_code=429,
        )
    pid = c.parent_id
    if pid is not None and not await db.parent_exists(pid):
        pid = None
    com = await db.add_comment(_clean_nick(c.nick), body, pid, c.token)
    _last_post[c.token] = now
    _prune_rate()
    await hub.broadcast({"type": "comment_new", "comment": com})
    return com


@app.put("/api/comments/{cid}")
async def api_edit_comment(cid: int, e: EditIn):
    if not db.enabled():
        return JSONResponse({"error": "comentarios no configurados"}, status_code=503)
    body = _clean_body(e.body)
    if not body:
        return JSONResponse({"error": "vacio"}, status_code=400)
    com = await db.edit_comment(cid, body, e.token)
    if com is None:
        return JSONResponse({"error": "no permitido"}, status_code=403)
    await hub.broadcast({"type": "comment_edit", "comment": com})
    return com


@app.delete("/api/comments/{cid}")
async def api_delete_comment(cid: int, token: str = "", admin_key: str = ""):
    if not db.enabled():
        return JSONResponse({"error": "comentarios no configurados"}, status_code=503)
    admin = bool(ADMIN_KEY) and admin_key == ADMIN_KEY
    ok = await db.delete_comment(cid, token, admin)
    if not ok:
        return JSONResponse({"error": "no permitido"}, status_code=403)
    await hub.broadcast({"type": "comment_del", "id": cid})
    return {"ok": True}


@app.post("/api/comments/{cid}/like")
async def api_like(cid: int, l: LikeIn):
    if not db.enabled():
        return JSONResponse({"error": "comentarios no configurados"}, status_code=503)
    n = await db.like_comment(cid, l.token, True)
    await hub.broadcast({"type": "comment_like", "id": cid, "likes": n})
    return {"likes": n}


@app.delete("/api/comments/{cid}/like")
async def api_unlike(cid: int, token: str = ""):
    if not db.enabled():
        return JSONResponse({"error": "comentarios no configurados"}, status_code=503)
    n = await db.like_comment(cid, token, False)
    await hub.broadcast({"type": "comment_like", "id": cid, "likes": n})
    return {"likes": n}


TEST_HTML = """<!doctype html><meta charset="utf-8">
<title>RUGWC backend</title>
<body style="font-family:monospace;background:#070b12;color:#cfe3e0;padding:24px;font-size:18px">
<h3 style="color:#ffb02e">RUG WORLD CUP 26 - motor en vivo</h3>
<div id="round" style="color:#36e0d0;margin-bottom:10px">conectando...</div>
<div id="match" style="font-size:28px;margin:10px 0"></div>
<div id="champ" style="color:#ffb02e;font-size:22px;margin-top:14px"></div>
<script>
var proto = location.protocol === "https:" ? "wss" : "ws";
var ws = new WebSocket(proto + "://" + location.host + "/ws");
ws.onmessage = function(e){
  var s = JSON.parse(e.data);
  document.getElementById("round").textContent =
    "EN VIVO - " + s.ronda + " - Partido " + s.partido + "/" + s.partidos_ronda + " - min " + s.minuto + "'";
  document.getElementById("match").innerHTML =
    '<span style="color:' + s.local.color + '">' + s.local.short + '</span> ' +
    s.local.goles + ' - ' + s.visita.goles +
    ' <span style="color:' + s.visita.color + '">' + s.visita.short + '</span>';
  document.getElementById("champ").textContent = s.campeon ? ("CAMPEON: " + s.campeon) : "";
};
ws.onclose = function(){ document.getElementById("round").textContent = "desconectado"; };
</script>
</body>"""


@app.get("/test", response_class=HTMLResponse)
async def test_page():
    return TEST_HTML
