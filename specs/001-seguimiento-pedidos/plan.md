# Plan técnico — Spec 001

## Arquitectura
Un solo servicio (contenedor) para ahorrar memoria en el servidor:

```
Navegador ──HTTPS──> Cloudflare Tunnel ──> Orange Pi :5210
                                             └─ FastAPI (uvicorn)
                                                 ├─ /            interfaz (HTML/CSS/JS estáticos)
                                                 ├─ /api/...     API JSON
                                                 └─ SQLAlchemy ──> PostgreSQL (base "pedidos")
                                                 └─ ai.py ──> Claude API (opcional)
```

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Dominio | `domain.py` | Reglas puras: división, transiciones, avance. Sin BD. |
| Modelos | `models.py` | Tablas SQLAlchemy. |
| Servicios | `services.py` | Casos de uso con transacción; traducen errores de dominio. |
| API | `routes.py`, `schemas.py` | Contrato HTTP y validación (Pydantic estricto). |
| IA | `ai.py` | Proveedores Gemini y Claude con respaldo, prompts y salida estructurada. |
| Config | `config.py`, `db.py` | Variables de entorno, motor y sesiones. |

## Tecnología
Python 3.13, FastAPI, SQLAlchemy 2, Pydantic 2, psycopg 3, uv,
Gemini por REST con `httpx` (modelo `gemini-3.5-flash-lite`, `GEMINI_MODEL`) y
SDK `anthropic` (modelo `claude-haiku-5-5`, `AI_MODEL`), orden en `AI_ORDER`, pytest + httpx. Frontend sin framework ni paso de compilación.

## Modelo de datos
```
pedidos
  id            PK
  numero        varchar(40)  -- como lo escribió el usuario
  numero_clave  varchar(40) UNIQUE  -- numero.strip().upper(), RF-04
  cliente       varchar(120)
  cantidad      int  CHECK (cantidad > 0)
  creado_en     timestamptz

paquetes
  id         PK
  pedido_id  FK -> pedidos ON DELETE CASCADE
  indice     int            -- 1..n
  unidades   int CHECK (unidades BETWEEN 1 AND 100)
  estado     varchar(20)    -- pendiente | en_proceso | revision | listo
  actualizado_en timestamptz
  UNIQUE (pedido_id, indice)

eventos_paquete
  id, paquete_id FK, accion ('avanzar'|'rechazar'),
  estado_origen, estado_destino, motivo NULL, creado_en
```
Las tablas se crean al iniciar (`Base.metadata.create_all`); no hace falta
herramienta de migraciones para este alcance.

## Reglas en `domain.py`
```python
ESTADOS = ["pendiente", "en_proceso", "revision", "listo"]
dividir_en_paquetes(cantidad) -> list[int]
siguiente_estado(estado) -> str          # TransicionInvalida si es "listo"
estado_tras_rechazo(estado) -> str       # TransicionInvalida si no es "revision"
resumen(paquetes) -> {conteo por estado, unidades_listas, total, avance}
```

## Contrato de la API
| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| GET | `/health` | 200 `{"status":"ok"}` | |
| GET | `/api/pedidos` | 200 lista con resumen | |
| POST | `/api/pedidos` | 201 pedido con paquetes y resumen | 422 validación, 409 duplicado |
| GET | `/api/pedidos/{numero}` | 200 detalle | 404 |
| POST | `/api/paquetes/{id}/avanzar` | 200 paquete + resumen del pedido | 404, 409 |
| POST | `/api/paquetes/{id}/rechazar` `{motivo?}` | 200 igual | 404, 409, 422 |
| GET | `/api/paquetes/{id}/historial` | 200 eventos | 404 |
| GET | `/api/ia/estado` | 200 `{"disponible": bool, "modelo": str}` | |
| POST | `/api/ia/interpretar` `{texto}` | 200 borrador `{numero, cliente, cantidad, faltantes, nota}` | 422, 503 |
| POST | `/api/ia/resumen` `{numero?}` | 200 `{texto}` | 404, 503 |

Formato de error: `{"detail": "mensaje en español"}`; los 422 de validación
se traducen a un mensaje legible por campo.

`cantidad` usa `StrictInt` de Pydantic (rechaza `"10"`, `2.5`, `true`) con
`gt=0, le=100000`.

## Concurrencia (RNF-03)
`avanzar` y `rechazar` leen el paquete con `SELECT ... FOR UPDATE`
(`with_for_update()`); en SQLite se ignora y no hace falta por ser un solo
escritor.

## IA
- `interpretar`: `client.messages.parse(output_format=BorradorIA)`; el
  modelo devuelve campos nulos si no los encuentra. El servidor valida el
  borrador con las mismas reglas y lo devuelve, **no lo guarda**.
- `resumen`: se envía un JSON compacto con los pedidos y sus conteos,
  avance y rechazos; se pide un informe de máximo ~120 palabras en español.
- El texto del usuario va como dato dentro de etiquetas, no como
  instrucción. Errores del SDK → 503.
- Pruebas: se inyecta un cliente falso (sin red).
- **Proveedores (RF-13):** `ProveedorGemini` llama a
  `POST /v1beta/models/{modelo}:generateContent` con `httpx` (header
  `x-goog-api-key`, `responseMimeType=application/json` + `responseSchema`
  para el borrador); no agrega dependencias. `ProveedorAnthropic` envuelve el
  SDK. Ambos traducen sus errores a `IANoDisponible`. `AsistenteIA` recibe la
  lista ordenada y, ante `IANoDisponible`, pasa al siguiente; recuerda cuál
  respondió para informarlo. Timeout por proveedor `AI_TIMEOUT` (20 s).

## Interfaz
Página única, mobile-first (una columna en teléfono, dos desde ~900 px).
Tokens de color en `:root`; el tema oscuro reusa los mismos tonos con otra
luminosidad. `data-theme` en `<html>` (sistema / claro / oscuro) con un
script en `<head>` que lo aplica antes de pintar y `localStorage` para
recordarlo. Encabezado con métricas globales, formulario de alta (+ caja
"Escribir con IA"), lista de pedidos con barra de avance y conteos, panel de
detalle con un tablero de 4 columnas (una por estado) con tarjetas de
paquete y botones Avanzar / Rechazar, historial por paquete y botón
"Resumen IA". Validación en el cliente solo como ayuda.

## Despliegue
- `Dockerfile` (python:3.13-slim + uv), `compose.yaml` con puerto 5210,
  `mem_limit: 200m`, `host.docker.internal` hacia el PostgreSQL del host.
- `deploy/deploy.sh`: rsync al servidor + `docker compose up -d --build`.
- Cloudflare Tunnel "Quantis": `pedidos.quantis.site → http://localhost:5210`.
- CI: GitHub Actions con `uv run pytest`.
