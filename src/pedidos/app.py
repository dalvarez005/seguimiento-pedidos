"""Aplicación FastAPI: API + interfaz estática."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .ai import AsistenteIA, IANoDisponible, desde_config
from .config import Settings, get_settings
from .db import Database
from .routes import router
from .services import Conflicto, NoEncontrado

STATIC = Path(__file__).parent / "static"

CAMPOS = {"numero": "Número de pedido", "cliente": "Cliente", "cantidad": "Cantidad",
          "motivo": "Motivo", "texto": "Texto"}


def _mensaje(err: dict) -> str:
    """Traduce un error de Pydantic a un mensaje en español (RF-03)."""
    loc = [str(x) for x in err.get("loc", ()) if x != "body"]
    campo = CAMPOS.get(loc[-1], loc[-1]) if loc else "Solicitud"
    tipo = err.get("type", "")
    ctx = err.get("ctx") or {}
    if campo == "Cantidad":
        if tipo in ("int_type", "int_parsing", "int_from_float", "missing"):
            return "Cantidad: debe ser un número entero mayor que cero."
        if tipo == "greater_than":
            return "Cantidad: debe ser mayor que cero."
        if tipo == "less_than_equal":
            return f"Cantidad: el máximo es {ctx.get('le'):,} unidades.".replace(",", " ")
    if tipo == "missing":
        return f"{campo}: es obligatorio."
    if tipo == "string_too_short":
        return f"{campo}: no puede estar vacío."
    if tipo == "string_too_long":
        return f"{campo}: máximo {ctx.get('max_length')} caracteres."
    if tipo == "string_type":
        return f"{campo}: debe ser texto."
    if tipo == "json_invalid":
        return "El cuerpo de la solicitud no es JSON válido."
    return f"{campo}: valor no válido."


def create_app(settings: Settings | None = None, ia: AsistenteIA | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db.crear_tablas()
        yield
        app.state.db.engine.dispose()

    app = FastAPI(title="Seguimiento de Pedidos", version="1.0.0", lifespan=lifespan)
    app.state.db = Database(settings.database_url)
    app.state.ia = ia or desde_config(settings)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError):
        errores = [_mensaje(e) for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": " ".join(errores), "errores": errores})

    @app.exception_handler(NoEncontrado)
    async def _404(_: Request, exc: NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Conflicto)
    async def _409(_: Request, exc: Conflicto):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(IANoDisponible)
    async def _503(_: Request, exc: IANoDisponible):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
