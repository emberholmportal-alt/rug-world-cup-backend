# RUG WORLD CUP 26 — Frontend: página LIVE + formato mundial

## Contexto
La página es **solo una transmisión en vivo** (broadcast). El motor del backend pasó a **formato
mundial real**: fase de grupos (12 grupos de 4) → eliminatorias desde 32avos → 3er puesto = 104
partidos, **buy-driven** (arranca con la primera compra). Dos cosas a la vez en este trabajo:
(A) rediseñar la UI para que sea live-only (sin menú de pestañas, sin barra de comentarios), y
(B) cablear esa UI a la data nueva del server.

## Backend (ya validado y desplegado — NO tocar)
El WebSocket (`BACKEND_WS`) manda TRES tipos de mensaje:

### `{type:"state", ...}` (cada tick) — el partido en vivo
- `fase`: `"grupos"` o `"ko"`.
- `ronda`: grupos → `"Fase de grupos"`; eliminatoria → `"16avos de final"` / `"Octavos de final"` /
  `"Cuartos de final"` / `"Semifinal"` / `"Final"` / `"Tercer puesto"`.
- `fecha`: nº de fecha (1-3) en grupos, `null` en eliminatoria.
- `grupo`: letra del grupo del partido en vivo (`"A"`..`"L"`) en grupos, `null` en eliminatoria.
- `partido` / `partidos_ronda`: nº del partido y total de la fase/ronda.
- (igual que antes) `minuto`, `energia`, `activo`, `buys`, `sol_max`, `bver`,
  `local`/`visita` (short/name/color/goles/atk), `campeon`, `tercero`.

### `{type:"groups", fase, grupos:[...]}` (al conectar + cuando cambia)
12 grupos con su tabla (ordenada por pts desc, desempate dif. gol, luego gf):
```json
{ "type":"groups", "fase":"grupos",
  "grupos":[ { "grupo":"A", "tabla":[
     {"short":"BTC","name":"Bitcoin","color":"#f7931a",
      "pj":3,"g":2,"e":1,"p":0,"gf":5,"gc":2,"dg":3,"pts":7,"pos":1}, ... 4 filas ...
  ]}, ... 12 grupos ... ] }
```

### `{type:"bracket", rounds:[...], campeon, tercero}` (al conectar + cuando cambia)
Cuadro de eliminatorias. **Vacío (`rounds:[]`) en fase de grupos**; se llena al empezar las
eliminatorias. Formato: rounds con `size`/`name`/`matches[{a,b,ga,gb,win,st}]` (st = done/live/next).

## A) Rediseño UI — la página es SOLO live

1. **Sacar el menú lateral** completo: los botones LIVE / GROUPS / TABLE / BRACKET / FEED / CHAT /
   HOW TO y todo el ruteo por secciones (`renderScreen` por sección, etc.). Ya no se navega.

2. **Sacar la barra inferior de comentarios** por completo: arrays de mensajes truchos, su seed, y el
   DOM del ticker inferior. (El ticker de titulares satíricos de ARRIBA puede quedar si querés; lo que
   se va es la barra de comentarios de abajo.)

3. **En el lugar del menú, un panel compacto AUTO-ROTATIVO** — mismo footprint que tenía el menú
   (misma columna izquierda, mismo alto/ancho aprox., **NO más grande**). Rota solo cada ~5s mostrando
   el estado del torneo con la data del server. Vistas que va ciclando:
   - **AHORA**: fase + partido en vivo. Grupos → "FASE DE GRUPOS · Fecha {fecha} · Grupo {grupo}".
     Eliminatoria → "{ronda} · Partido {partido}/{partidos_ronda}". Con los 2 equipos y el marcador.
   - **GRUPOS** (durante la fase de grupos): rota por los 12 grupos (A→L), cada slide con la tabla del
     grupo (4 equipos: Pts y DG), resaltando los **2 primeros** (clasifican). Tip: arrancá por el grupo
     del partido en vivo.
   - **CUADRO** (durante eliminatorias): el avance del cuadro (quién pasó de ronda) y, al final, el
     **campeón** y el **3er puesto** (`campeon`/`tercero`).
   - Indicá visualmente que rota (ej. puntitos abajo). Por defecto pasivo (se mira, no se toca);
     opcional que un click pause/avance.

4. **Eliminá la lógica vieja local** de grupos/tabla (`computeGroups`, `derive()` sobre `S.vol`/`S.sold`).
   Todo sale de la data real del server (`S.srvGroups` desde el mensaje `groups`, `S.srvBracket` desde
   `bracket`, y el snapshot).

5. **HUD del partido** (cartelito arriba a la izquierda con marcador + minuto): puede mostrar también la
   fase/grupo desde el snapshot.

## B) Wiring de datos
- En el `onmessage` del WS (ya rutea `state`/`bracket`) agregá el caso `groups` → guardar en `S.srvGroups`
  y refrescar el panel.
- El panel se redibuja con cada `state`/`groups`/`bracket` y con su propio timer de rotación.

## Cómo probar
Abrir `index.html`. Buy-driven: hasta la primera compra está congelado (Fase de grupos, min 0). Para
moverlo en dev: en el backend seteá la env `DEV_KEY` y pegá `…onrender.com/api/dev/buy?sol=0.5&key=TUCLAVE`
varias veces. Verificá: el panel rota mostrando los 12 grupos llenándose, el "AHORA" dice fase/grupo/fecha
correctos, y al terminar los 72 de grupos el panel pasa a mostrar el CUADRO de eliminatorias.

## Validación
- No leas el index entero; grep/secciones. Extraé el `<script>` grande y corré `node --check`.
- Un solo commit. Mostrame el diff antes.
