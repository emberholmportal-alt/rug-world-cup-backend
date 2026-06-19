# RUG WORLD CUP 26 — Frontend: formato mundial (grupos + eliminatorias)

## Contexto
El motor del backend pasó a **formato mundial real**: fase de grupos (12 grupos de 4) →
eliminatorias desde 32avos → partido por el 3er puesto = **104 partidos**. Es **buy-driven**:
arranca con la primera compra y avanza con la actividad. Hay que cablear `index.html` para que
consuma esta nueva data del server.

## Backend (ya validado y desplegado — NO tocar)
El WebSocket (`BACKEND_WS`) ahora manda TRES tipos de mensaje:

### `{type:"state", ...}` (cada tick) — el partido en vivo
Campos nuevos respecto de antes:
- `fase`: `"grupos"` o `"ko"`.
- `ronda`: en grupos `"Fase de grupos"`; en eliminatoria `"16avos de final"` / `"Octavos de final"` /
  `"Cuartos de final"` / `"Semifinal"` / `"Final"` / `"Tercer puesto"`.
- `fecha`: número de fecha (1-3) en fase de grupos, `null` en eliminatoria.
- `grupo`: letra del grupo del partido en vivo (`"A"`..`"L"`) en grupos, `null` en eliminatoria.
- `partido` / `partidos_ronda`: número del partido y total de la fase/ronda.
- (siguen igual) `minuto`, `energia`, `activo`, `buys`, `sol_max`, `bver`,
  `local`/`visita` (short/name/color/goles/atk), `campeon`, `tercero`.

### `{type:"groups", fase, grupos:[...]}` (al conectar + cuando cambia algo)
Los 12 grupos con su tabla (ordenada por pts desc, desempate dif. de gol, luego goles a favor):
```json
{ "type":"groups", "fase":"grupos",
  "grupos":[ { "grupo":"A", "tabla":[
     {"short":"BTC","name":"Bitcoin","color":"#f7931a",
      "pj":3,"g":2,"e":1,"p":0,"gf":5,"gc":2,"dg":3,"pts":7,"pos":1},
     ... 4 filas ...
  ]}, ... 12 grupos ... ] }
```

### `{type:"bracket", rounds:[...], campeon, tercero}` (al conectar + cuando cambia)
El cuadro de eliminatorias. **Vacío (`rounds:[]`) durante la fase de grupos**; se llena al empezar
las eliminatorias. Formato igual al que ya consume `renderFixture` (rounds con `size`/`name`/
`matches[{a,b,ga,gb,win,st}]`, donde `st` es `done`/`live`/`next`). `tercero` = chain del 3er puesto.

## Tareas en `index.html`

1. **Manejar el mensaje `groups`** en el `onmessage` del WS: guardarlo (ej. `S.srvGroups`) y re-render
   de las pestañas Grupos/Tabla si están abiertas. (El `onmessage` ya rutea `state`/`bracket`; agregar `groups`.)

2. **Pestaña GRUPOS** — reescribir para dibujar desde `S.srvGroups` (los 12 grupos reales del server).
   **Eliminar** la lógica vieja local que computa grupos sobre `S.vol`/`S.points` (tipo `computeGroups`).
   Mostrar los 12 grupos con su tabla (equipo, PJ, G, E, P, DG, Pts), resaltando los **2 primeros** de cada
   grupo (clasifican directo). Opcional: marcar la zona de "mejores terceros".

3. **Pestaña TABLA** — reescribir para mostrar una tabla global derivada de `S.srvGroups`. Sugerencia:
   las 48 chains ordenadas por pts (y desempates), marcando los 32 clasificados. **Eliminar** la lógica
   vieja local (`derive()` sobre `S.sold`). (Si te parece mejor otra vista, dale, pero que salga de la data real.)

4. **Etiqueta del partido en vivo** (EN VIVO / HUD) — componer el label desde los campos nuevos del snapshot:
   - en grupos: `"Fase de grupos · Grupo {grupo} · Fecha {fecha}"`
   - en eliminatoria: `"{ronda} · Partido {partido}/{partidos_ronda}"`

5. **Pestaña FIXTURE** — `renderFixture` ya dibuja desde `S.srvBracket` y los nombres de ronda ya están.
   Solo dos cosas: durante la fase de grupos el bracket llega vacío, así que en vez de "esperando datos del
   torneo…" mostrar algo como "Fase de grupos en curso — el cuadro se arma al terminar los grupos". Y mostrar
   el **campeón** y el **tercero** (campos `campeon`/`tercero`) cuando estén definidos.

6. **Chat fake** — si todavía quedara algo de chat trucho/comentarios, sacarlo (no hay feature de comentarios;
   pump.fun ya los tiene). El **ticker** (barra inferior) alimentalo SOLO con eventos reales del torneo desde
   `applyState`: goles y cambios de ronda/fase.

## Cómo probar
Abrir `index.html`. Como es buy-driven, hasta la primera compra está congelado (Fase de grupos, min 0).
Para moverlo en dev: en el backend seteá la env `DEV_KEY` en Render y pegá
`…onrender.com/api/dev/buy?sol=0.5&key=TUCLAVE` varias veces. Verificá: la pestaña GRUPOS muestra los 12
grupos llenándose, la TABLA refleja lo mismo, el label del partido dice fase/grupo/fecha correctos, y al
terminar los 72 partidos de grupos el FIXTURE arma el cuadro de 32avos.

## Validación
- No leas el index entero; grep/secciones. Extraé el `<script>` grande y corré `node --check`.
- Un solo commit al final. Mostrame el diff antes de commitear.
