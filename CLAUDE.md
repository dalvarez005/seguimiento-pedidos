# Constitución del proyecto — Seguimiento de Pedidos

Reglas que el agente de IA (Claude Code) sigue en este repositorio. Se aplica
Spec-Driven Development: **la especificación manda sobre el código**.

## Flujo SDD
1. Todo cambio de comportamiento empieza en `specs/<feature>/spec.md`
   (requisito + criterio de aceptación). Si el código y la spec no coinciden,
   se corrige el código o se actualiza primero la spec, nunca en silencio.
2. `plan.md` define arquitectura, modelo de datos y contrato de la API.
3. `tasks.md` lista tareas pequeñas (T01, T02…). Se implementan en orden, se
   marcan `[x]` al terminarlas y el commit cita la tarea.
4. Cada requisito funcional (RF-xx) tiene al menos una prueba que lo nombra.

## Reglas de código
- Lógica de negocio pura en `src/pedidos/domain.py` (sin BD ni HTTP), probada
  de forma unitaria. Servicios y rutas solo orquestan.
- Las reglas se validan en el servidor; la interfaz solo ayuda al usuario.
- Nada de secretos en el repo: van en `.env` (ver `.env.example`).
- La IA nunca escribe en la base de datos por su cuenta: propone y el
  usuario confirma.
- `uv run pytest` debe pasar antes de cada commit.
- Textos de la interfaz y mensajes de error en español.

## Comandos
- `uv sync` — instala dependencias
- `uv run uvicorn pedidos.app:app --reload` — servidor local (http://localhost:8000)
- `uv run pytest` — pruebas
- `deploy/deploy.sh` — despliegue a la Orange Pi
