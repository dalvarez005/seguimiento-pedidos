# Seguimiento de Pedidos

Aplicación web para registrar pedidos, dividirlos automáticamente en paquetes
de hasta 100 unidades y seguir el avance de cada paquete por los estados
**Pendiente → En proceso → Revisión → Listo**.

- **App publicada:** https://pedidos.quantis.site
- **Repositorio:** https://github.com/dalvarez005/seguimiento-pedidos

Hecha con **Spec-Driven Development (SDD)** usando **Claude Code** como agente
de IA.

## Funcionalidades

| Requisito de la prueba | Cómo se cumple |
|---|---|
| Crear pedido con número, cliente y cantidad; dividir en paquetes de hasta 100 | `POST /api/pedidos`. 250 → 100, 100, 50. El formulario muestra la división antes de guardar. |
| Cantidad entera > 0 y número de pedido único | Validación estricta en el servidor (rechaza `0`, negativos, `2.5`, `"10"`, `true`…) y restricción `UNIQUE` en la base. El número no distingue mayúsculas ni espacios (`ped-1` = `PED-1`). |
| Avanzar por estados sin saltar ni regresar | Solo existe la acción "avanzar al siguiente". Bloqueo de fila en PostgreSQL para que dos clics simultáneos no salten un estado. |
| Rechazar en Revisión → En proceso | Solo en Revisión, con motivo opcional. |
| Conteo por estado y % de avance por unidades | Lista y detalle muestran paquetes por estado y avance = unidades listas / total (p. ej. 250 con el paquete de 50 listo = 20 %, no 33 %). |
| Persistencia | PostgreSQL en producción, SQLite en desarrollo. |

**Extras**

- **Crear pedido con IA:** escribes *"pedido PED-1042 para Ferretería López,
  doscientas cincuenta unidades"* y la IA llena el formulario (salida
  estructurada). La IA solo propone: el usuario revisa y confirma. Avisa si el
  número ya existe o si falta algún dato.
- **Resumen con IA:** informe breve del avance de un pedido o de todos, con
  cuellos de botella, rechazos y la siguiente acción sugerida.
- **IA con respaldo (RF-13):** primero Gemini (`gemini-3.5-flash-lite`, luego
  `gemini-3.1-flash-lite`) y, si falla (saturado, sin saldo, caído o lento),
  la misma solicitud pasa sola a Claude (`claude-haiku-5-5`). El encabezado
  muestra qué IA está activa y el resumen dice qué modelo lo generó.
- Si el servidor no tiene ninguna clave de IA, esas funciones se ocultan y el
  resto funciona igual.
- **Historial** de movimientos por paquete (quién pasó de qué estado a cuál,
  y motivo de rechazo).
- **Interfaz tipo casillero de clasificación:** cada estado es una casilla y
  cada paquete una ficha que se desliza a la siguiente al avanzar; lo que
  cambia queda marcado hasta que lo ves. Tema claro y oscuro con la misma
  paleta (sigue al sistema y se cambia con un botón que se recuerda),
  responsive desde 320 px (en el celular las casillas son pestañas), contraste
  WCAG AA y navegación con teclado. Indicadores globales, búsqueda y enlace
  directo a un pedido (`/#PED-1001`). Sistema visual en `DESIGN.md`.

## Tecnología

Python 3.13 · FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Pydantic 2 · SDK
Gemini (REST con `httpx`) y `anthropic` (Claude Haiku 5.5) con respaldo · HTML/CSS/JS sin framework · pytest · Docker ·
GitHub Actions · Cloudflare Tunnel.

```
src/pedidos/
  domain.py     reglas de negocio puras (división, transiciones, avance)
  models.py     tablas: pedidos, paquetes, eventos_paquete
  services.py   casos de uso con transacción y bloqueo de fila
  routes.py     API JSON
  ai.py         funciones con Claude
  static/       interfaz
specs/001-seguimiento-pedidos/   spec.md, plan.md, tasks.md (SDD)
tests/          pruebas de dominio, API e IA
```

## Instalación

Requisitos: [uv](https://docs.astral.sh/uv/) (instala Python 3.13 por sí
solo).

```bash
git clone https://github.com/dalvarez005/seguimiento-pedidos.git
cd seguimiento-pedidos
uv sync
uv run uvicorn pedidos.app:app --reload
# http://localhost:8000
```

Sin configuración usa SQLite (`pedidos.db`). Para PostgreSQL o IA, copia
`.env.example` a `.env`:

```env
DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/pedidos
GEMINI_API_KEY=...             # opcional (Google AI Studio, nivel gratis)
ANTHROPIC_API_KEY=sk-ant-...   # opcional (respaldo)
AI_ORDER=gemini,anthropic      # orden de prueba; si uno falla, sigue el otro
```

Las tablas se crean solas al iniciar.

### Con Docker

```bash
cp .env.example .env   # y completa DATABASE_URL
docker compose up -d --build
# http://localhost:5210
```

### Despliegue (servidor propio)

La app corre en un servidor propio (Orange Pi, ARM64) dentro de Docker, junto
a un PostgreSQL que ya estaba ahí, y se publica con **Cloudflare Tunnel** en
`pedidos.quantis.site` (sin abrir puertos). `deploy/deploy.sh` corre las
pruebas, copia el código por rsync y reconstruye el contenedor.

## Pruebas

```bash
uv run pytest                      # SQLite temporal
TEST_DATABASE_URL=postgresql+psycopg://postgres:test@localhost:5432/pedidos_test \
  uv run pytest                    # PostgreSQL (incluye la prueba de concurrencia)
```

90 pruebas automatizadas, nombradas por requisito (`test_rf03_…`):

- **Dominio:** división (250, 100, 1, 99, 101, 1000), transiciones válidas e
  inválidas, rechazo, cálculo de avance y redondeo.
- **API:** validación de cada tipo de cantidad inválida, duplicados con
  mayúsculas y espacios, flujo completo hasta 100 %, rechazo y reingreso,
  persistencia tras reiniciar la app, historial.
- **Concurrencia:** 8 avances simultáneos sobre el mismo paquete → exactamente
  3 tienen éxito. Se comprobó que la prueba **falla** si se quita el bloqueo de
  fila.
- **IA:** con un cliente simulado (sin red ni costo): borrador, campos
  faltantes, número repetido, errores del servicio → 503, sin clave → 503.
- **Respaldo de IA (RF-13):** Gemini falla → responde Claude; ambos fallan →
  503; orden configurable; solicitud a Gemini y sus errores (429, 503,
  respuesta vacía o JSON inválido, tiempo agotado) con `httpx.MockTransport`.

El flujo de GitHub Actions (`.github/workflows/tests.yml`, corre todo en
SQLite y PostgreSQL) está listo, pero ver "Pendientes".

## Cómo se aplicó SDD

1. **Constitución** (`CLAUDE.md`): reglas fijas para el agente — la spec manda
   sobre el código, lógica de negocio pura y probada, cada requisito con su
   prueba, la IA nunca escribe en la base de datos.
2. **Especificación** (`spec.md`): historias de usuario, requisitos RF-01 a
   RF-12 con ejemplos y criterios de aceptación, fuera de alcance. Se hizo
   commit antes de escribir código.
3. **Plan** (`plan.md`): arquitectura, modelo de datos, contrato de la API,
   concurrencia y despliegue.
4. **Tareas** (`tasks.md`): T01–T13, implementadas en orden; cada commit cita
   su tarea (ver `git log`).
5. **Verificación:** pruebas primero en el dominio; las pruebas de API e IA
   citan el requisito que cubren.

## Error del agente de IA y cómo se corrigió

**Error principal: el resumen con IA ignoraba la regla "IA opcional" (RF-12).**

Al implementar `POST /api/ia/resumen`, el agente puso primero un atajo: *si no
hay pedidos, responder "Todavía no hay pedidos registrados"*, y solo después
llamaba a la IA. Con eso, en un servidor **sin** clave de IA el endpoint
respondía `200` en lugar de `503`, contradiciendo la spec (RF-12: sin clave,
las funciones de IA responden 503 y la interfaz las oculta).

- **Cómo se detectó:** la prueba `test_rf12_sin_clave_la_ia_no_esta_disponible`,
  escrita a partir de la spec, falló (`assert 200 == 503`).
- **Corrección:** se agregó `AsistenteIA.requerir()` y el endpoint lo llama
  antes que cualquier otra lógica (commit `feat(ia): T08 …`). La prueba quedó
  en verde y protege la regla.
- **Lección:** el agente optimizó un caso borde sin revisar la spec; escribir
  las pruebas desde los requisitos (y no desde el código) es lo que lo atrapó.

**Otros dos tropiezos menores del agente durante el desarrollo**

- **Paquete no instalado:** el agente corrió `uv sync` cuando `src/pedidos`
  aún no existía; las pruebas pasaban (usan `pythonpath`) pero el servidor
  fallaba con `ModuleNotFoundError: No module named 'pedidos'`. Se corrigió con
  `uv sync --reinstall-package pedidos`.
- **Imagen Docker de 533 MB:** el servidor solo tenía ~900 MB libres. La caché
  de `uv` quedaba dentro de la imagen; con `UV_NO_CACHE=1` y sin
  `uvicorn[standard]` la capa de dependencias bajó de 128 MB a 103 MB y se
  reutilizan las capas base que ya estaban en el servidor.

## Pendientes y posibles mejoras

Todos los requisitos de la prueba están implementados, probados y publicados.

- **Saldo de Claude:** la clave de Claude está configurada, pero la cuenta de
  la API no tiene crédito (la suscripción Claude Pro no lo incluye). Mientras
  tanto responde Gemini; Claude entra solo cuando se cargue saldo.

- **CI en GitHub Actions:** el archivo está escrito y probado localmente, pero
  no se pudo subir: el token de GitHub usado por el agente no tenía el permiso
  `workflow`, y GitHub rechaza esos archivos sin él. Se subirá en cuanto se
  autorice el permiso. Fuera de alcance por decisión de la spec:
autenticación de usuarios, edición/borrado de pedidos y migraciones de base de
datos versionadas (hoy las tablas se crean al iniciar).
