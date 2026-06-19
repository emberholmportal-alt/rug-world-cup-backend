# RUG WORLD CUP 26 — backend de transmisión en vivo
# Arranque mínimo: WebSocket + loop de estado + health check.
# El motor real del torneo (48 equipos) y la conexión a PumpPortal
# se suman en el próximo paso. Esto sirve para probar que el deploy
# en Render anda y que el WebSocket reparte el MISMO estado a todos.

import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse


# ---------------------------------------------------------------------------
# Estado autoritativo del torneo (placeholder; después crece al Mundial real)
# ---------------------------------------------------------------------------
class GameState:
    def __init__(self):
        self.tick = 0
        self.minuto = 0
        self.fase = "Octavos"
        self.partido = {"local": "SOL", "visitante": "ETH", "gl": 0, "gv": 0}

    def snapshot(self):
        return {
            "type": "state",
            "tick": self.tick,
            "minuto": self.minuto,
            "fase": self.fase,
            "partido": self.partido,
        }


state = GameState()


# ---------------------------------------------------------------------------
# Hub de conexiones: guarda los WebSocket abiertos y transmite a todos
# ---------------------------------------------------------------------------
class Hub:
    def __init__(self):
        self.conns = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)
        # al que entra le mandamos la foto del estado actual
        await ws.send_text(json.dumps(state.snapshot()))

    def disconnect(self, ws: WebSocket):
        self.conns.discard(ws)

    async def broadcast(self, msg: dict):
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


# ---------------------------------------------------------------------------
# Loop de simulación. Por ahora solo avanza un tick y transmite, para probar
# que el broadcast llega igual a todos. Acá adentro va a vivir el partido real.
# ---------------------------------------------------------------------------
async def sim_loop():
    while True:
        await asyncio.sleep(1.0)
        state.tick += 1
        state.minuto = (state.minuto + 1) % 91
        await hub.broadcast(state.snapshot())


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(sim_loop())
    yield
    tarea.cancel()


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
async def health():
    # Render usa esto como health check; también sirve para ver cuántos miran
    return {"ok": True, "viewers": len(hub.conns), "tick": state.tick}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            # por ahora solo mantenemos viva la conexión (después: chat entrante)
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


# Página de prueba: abrí /test en el navegador para VER el estado en vivo
@app.get("/test", response_class=HTMLResponse)
async def test_page():
    return """<!doctype html><meta charset="utf-8">
<title>RUGWC backend</title>
<body style="font-family:monospace;background:#070b12;color:#36e0d0;padding:24px;font-size:18px">
<h3 style="color:#ffb02e">RUG WORLD CUP 26 — test de conexión</h3>
<div id="log">conectando...</div>
<script>
var proto = location.protocol === "https:" ? "wss" : "ws";
var ws = new WebSocket(proto + "://" + location.host + "/ws");
var log = document.getElementById("log");
ws.onopen = function(){ log.innerHTML = "\u25cf conectado, esperando estado..."; };
ws.onmessage = function(e){
  var s = JSON.parse(e.data);
  log.innerHTML = "\u25cf EN VIVO \u00b7 tick " + s.tick +
    "<br>fase: " + s.fase + " \u00b7 minuto " + s.minuto + "'" +
    "<br>" + s.partido.local + " " + s.partido.gl + " - " + s.partido.gv + " " + s.partido.visitante;
};
ws.onclose = function(){ log.innerHTML += "<br>\u25cb desconectado"; };
</script>
</body>"""
