# RUG WORLD CUP 26 — Frontend: sección de comentarios

## Objetivo
Cablear una sección de **comentarios y respuestas** en `rug-world-cup.html`, conectada al
backend FastAPI (ya desplegado y andando), que se actualice **en vivo** y que vuelque cada
comentario nuevo en la **barra de comentarios (el ticker)** que ya existe en la página.

Mismo patrón que los comentarios del prode (`index__4_.html`): árbol por `parent_id`, likes,
responder, editar/borrar. **Diferencia clave**: el prode tiene login con badges (empresa/sector);
acá la página es **anónima**, se usa un nick elegido por el usuario.

---

## Backend (ya vivo — NO hay que tocarlo)
Base: `https://rug-world-cup-backend.onrender.com`

Endpoints REST:
- `GET /api/comments?limit=200` → array plano de comentarios, **más nuevos primero** (id desc).
  El front arma el árbol a partir de `parent_id`.
- `POST /api/comments` → body JSON `{ "nick": str, "body": str, "parent_id": int|null, "token": str }`.
  Devuelve el comentario creado. **429** si el mismo `token` postea dentro de 20s (body `{error, retry}`).
  **400** si el texto viene vacío.
- `PUT /api/comments/{id}` → body `{ "body": str, "token": str }`. Devuelve el comentario actualizado.
  **403** si el `token` no es el del autor.
- `DELETE /api/comments/{id}?token=XXX` (opcional `&admin_key=YYY` para moderación) → `{ok:true}`.
  **403** si no sos el autor ni admin.
- `POST /api/comments/{id}/like` → body `{ "token": str }` → `{likes: N}`.
- `DELETE /api/comments/{id}/like?token=XXX` → `{likes: N}`.

Forma del objeto comentario:
```json
{ "id": 12, "nick": "satoshi", "body": "gm rugbros", "parent_id": null,
  "created_at": "2026-06-19T18:00:00Z", "updated_at": null,
  "deleted": false, "likes": 3 }
```
Los borrados llegan con `"deleted": true` y `"body": ""` → renderizar como
"[comentario eliminado]" pero **seguir mostrando sus respuestas** (no colapsar la rama).

CORS ya está abierto (`allow_origins=*`), así que el `fetch` desde el front funciona sin problema.

---

## WebSocket (ya conectado en el HTML)
El HTML ya abre el WS a `BACKEND_WS` (`wss://rug-world-cup-backend.onrender.com/ws`) y su
`onmessage` ya maneja `type:"state"` y `type:"bracket"`. El **mismo WS** ahora empuja eventos de
comentarios — hay que agregar estos casos al `onmessage`:

- `{type:"comment_new",  comment:{...}}` → comentario o respuesta nueva.
- `{type:"comment_edit", comment:{...}}` → editado.
- `{type:"comment_del",  id}` → borrado (soft).
- `{type:"comment_like", id, likes}` → cambió el conteo de likes.

Con esto aparecen **al instante en todos** los que están mirando, sin polling.

---

## Comportamiento del front

1. **Convertir la sección "chat" actual en "comentarios"**: form de carga (textarea + botón Enviar)
   arriba, y abajo el árbol de comentarios — top-level más nuevos arriba, respuestas anidadas
   cronológicas, "Responder" en cada uno, corazón de like con contador, y editar/borrar SOLO en los propios.

2. **Identidad sin login**:
   - Nick elegido por el usuario, guardado en `localStorage["rwc_nick"]` (pedirlo la primera vez
     que intenta postear; debe poder cambiarlo).
   - `author_token`: random por navegador (ej. `crypto.randomUUID()`), guardado en
     `localStorage["rwc_token"]`. Se manda en cada `POST`/`PUT`/`DELETE`/`like`. Sirve para editar/borrar
     lo propio y para el dedupe de likes del lado del server.
   - Guardar en localStorage qué comentarios likeó este navegador (set de ids) para pintar el corazón.

3. **Al cargar la página**: `GET /api/comments` para poblar la lista inicial.

4. **En vivo (vía WS)**:
   - `comment_new` → insertar arriba (o anidar bajo su `parent_id` si es respuesta) **y** empujar al ticker.
   - `comment_edit` / `comment_del` / `comment_like` → actualizar ese comentario en su lugar.
   - Importante: cuando VOS posteás, el POST ya te devuelve el comentario Y además te va a llegar por el
     WS (porque el server lo emite a todos, incluido vos). Evitá duplicarlo: deduplicá por `id` al insertar.

5. **Alimentar el ticker (la barra de comentarios)**: cada comentario nuevo entra al ticker que ya existe
   en la página. **Eliminar** el chat trucho actual (los arrays tipo `CHAT_USERS`/`CHAT_MSGS` y el seed de
   mensajes falsos) y reemplazarlo por comentarios reales. Borrar también el código viejo de Supabase
   (`initRealChat`) si quedó, que no se usa.

6. **Antispam UX**: si el `POST` devuelve **429**, mostrar "esperá unos segundos" y deshabilitar el botón
   Enviar el tiempo que diga `retry`.

7. **Seguridad**: **escapar** el texto del comentario y el nick al renderizar (es input público → XSS).
   El prode usa una función `_escHtml` simple; replicar.

---

## Puntos de integración en `rug-world-cup.html`
(grepear el archivo para ubicarlos exacto — los nombres pueden variar)

- **WS `onmessage`**: donde dice
  `if(s&&s.type==="state") applyState(s); else if(s&&s.type==="bracket") applyBracket(s);`
  → agregar `else if(s.type==="comment_new") ...` etc.
- **Constantes**: `BACKEND_WS` ya está. Agregar `BACKEND_HTTP = "https://rug-world-cup-backend.onrender.com"`
  para los `fetch`.
- **Sistema de chat actual**: las funciones que renderizan la caja de chat y el panel lateral, la función
  que pushea al chat/ticker, y el ticker (la barra de comentarios). Eso es lo que se reconvierte/alimenta.
- **Router de pestañas**: la sección/tab "chat" pasa a ser "comentarios".

---

## Cómo probarlo
Abrir `rug-world-cup.html` en el navegador (conecta solo al backend vivo). Postear un comentario,
responder, dar like. Abrir una segunda pestaña: el comentario tiene que aparecer en las dos al instante,
y entrar en el ticker. Recargar: el historial se carga vía `GET /api/comments`.

## Referencia
`index__4_.html` (el prode) tiene la implementación completa de este patrón de comentarios — copiar la
estructura de render del árbol, los botones, y `_escHtml`. Quitar todo lo de login/badges/usuario logueado.
