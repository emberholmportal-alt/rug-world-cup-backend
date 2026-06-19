# RUG WORLD CUP 26 — backend de transmisión en vivo
# Motor real del torneo (48 chains, eliminación directa) corriendo en el server
# y transmitido por WebSocket a todos. PumpPortal se conecta en el próximo paso.

import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from engine import Tournament

torneo = Tournament()


class Hub:
    def __init__(self):
        self.conns = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)
        await ws.send_text(json.dumps(torneo.snapshot()))

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
    while True:
        await asyncio.sleep(1.0)
        torneo.tick()
        await hub.broadcast(torneo.snapshot())


@asynccontextmanager
async def lifespan(app):
    tarea = asyncio.create_task(sim_loop())
    yield
    tarea.cancel()


app = FastAPI(lifespan=lifespan)


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


@app.get("/test", response_class=HTMLResponse)
async def test_page():
    return """<!doctype html><meta charset="utf-8">
<title>RUGWC backend</title>
<body style="font-family:monospace;background:#070b12;color:#cfe3e0;padding:24px;font-size:18px">
<h3 style="color:#ffb02e">RUG WORLD CUP 26 \u2014 motor en vivo</h3>
<div id="round" style="color:#36e0d0;margin-bottom:10px">conectando...</div>
<div id="match" style="font-size:28px;margin:10px 0"></div>
<div id="champ" style="color:#ffb02e;font-size:22px;margin-top:14px"></div>
<script>
var proto = location.protocol === "https:" ? "wss" : "ws";
var ws = new WebSocket(proto + "://" + location.host + "/ws");
ws.onmessage = function(e){
  var s = JSON.parse(e.data);
  document.getElementById("round").textContent =
    "\u25cf " + s.ronda + " \u00b7 Partido " + s.partido + "/" + s.partidos_ronda + " \u00b7 min " + s.minuto + "'";
  document.getElementById("match").innerHTML =
    '<span style="color:' + s.local.color + '">' + s.local.short + '</span> ' +
    s.local.goles + ' - ' + s.visita.goles +
    ' <span style="color:' + s.visita.color + '">' + s.visita.short + '</span>';
  document.getElementById("champ").textContent = s.campeon ? ("\ud83c\udfc6 CAMPE\u00d3N: " + s.campeon) : "";
};
ws.onclose = function(){ document.getElementById("round").textContent = "\u25cb desconectado"; };
</script>
</body>"""
