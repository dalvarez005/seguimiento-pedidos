"""Rutas HTTP (contrato en plan.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import services as sv
from .ai import AsistenteIA
from .domain import NOMBRES
from .models import Pedido
from .schemas import (
    LIMITE_UNIDADES,
    Borrador,
    EstadoIA,
    EventoSalida,
    InterpretarEntrada,
    MovimientoSalida,
    PaqueteSalida,
    PedidoCrear,
    PedidoDetalle,
    PedidoSalida,
    RechazoEntrada,
    ResumenIAEntrada,
    ResumenIASalida,
)

router = APIRouter(prefix="/api")


def sesion(request: Request):
    yield from request.app.state.db.sesion()


def asistente(request: Request) -> AsistenteIA:
    return request.app.state.ia


DB = Annotated[Session, Depends(sesion)]
IA = Annotated[AsistenteIA, Depends(asistente)]


def a_salida(p: Pedido, rechazos: int = 0) -> PedidoSalida:
    return PedidoSalida(
        id=p.id,
        numero=p.numero,
        cliente=p.cliente,
        cantidad=p.cantidad,
        creado_en=p.creado_en,
        resumen=sv.resumen_pedido(p),
        rechazos=rechazos,
    )


def a_detalle(s: Session, p: Pedido) -> PedidoDetalle:
    rechazos = sv.rechazos_por_pedido(s).get(p.id, 0)
    return PedidoDetalle(
        **a_salida(p, rechazos).model_dump(),
        paquetes=[PaqueteSalida.model_validate(x) for x in p.paquetes],
    )


@router.get("/pedidos", response_model=list[PedidoSalida])
def listar(s: DB):
    rechazos = sv.rechazos_por_pedido(s)
    return [a_salida(p, rechazos.get(p.id, 0)) for p in sv.listar_pedidos(s)]


@router.post("/pedidos", response_model=PedidoDetalle, status_code=201)
def crear(datos: PedidoCrear, s: DB):
    return a_detalle(s, sv.crear_pedido(s, datos))


@router.get("/pedidos/{numero}", response_model=PedidoDetalle)
def detalle(numero: str, s: DB):
    return a_detalle(s, sv.obtener_pedido(s, numero))


def _movimiento(s: Session, paquete) -> MovimientoSalida:
    pedido = paquete.pedido
    rechazos = sv.rechazos_por_pedido(s).get(pedido.id, 0)
    return MovimientoSalida(
        paquete=PaqueteSalida.model_validate(paquete), pedido=a_salida(pedido, rechazos)
    )


@router.post("/paquetes/{paquete_id}/avanzar", response_model=MovimientoSalida)
def avanzar(paquete_id: int, s: DB):
    return _movimiento(s, sv.avanzar(s, paquete_id))


@router.post("/paquetes/{paquete_id}/rechazar", response_model=MovimientoSalida)
def rechazar(paquete_id: int, s: DB, datos: RechazoEntrada | None = None):
    motivo = datos.motivo if datos else None
    return _movimiento(s, sv.rechazar(s, paquete_id, motivo))


@router.get("/paquetes/{paquete_id}/historial", response_model=list[EventoSalida])
def historial(paquete_id: int, s: DB):
    return sv.historial(s, paquete_id)


# --- IA (extra) ---
@router.get("/ia/estado", response_model=EstadoIA)
def estado_ia(ia: IA):
    return EstadoIA(disponible=ia.disponible, modelo=ia.modelo if ia.disponible else None)


@router.post("/ia/interpretar", response_model=Borrador)
def interpretar(datos: InterpretarEntrada, ia: IA, s: DB):
    crudo = ia.interpretar(datos.texto)
    b = Borrador(nota=crudo.get("nota"))
    notas = [b.nota] if b.nota else []

    # Mismas reglas que el alta: lo que no cumpla se deja vacío para que el
    # usuario lo complete.
    numero = (crudo.get("numero") or "").strip()
    if numero and len(numero) <= 40:
        b.numero = numero
        try:
            sv.obtener_pedido(s, numero)
            notas.append(f"Ojo: el número {numero} ya existe.")
        except sv.NoEncontrado:
            pass
    cliente = (crudo.get("cliente") or "").strip()
    if cliente:
        b.cliente = cliente[:120]
    cantidad = crudo.get("cantidad")
    if isinstance(cantidad, int) and 0 < cantidad <= LIMITE_UNIDADES:
        b.cantidad = cantidad
    elif cantidad is not None:
        notas.append(f"La cantidad {cantidad} no es válida.")

    b.faltantes = [c for c in ("numero", "cliente", "cantidad") if getattr(b, c) is None]
    b.nota = " ".join(notas) or None
    return b


@router.post("/ia/resumen", response_model=ResumenIASalida)
def resumen_ia(ia: IA, s: DB, datos: ResumenIAEntrada | None = None):
    if datos and datos.numero:
        pedidos = [sv.obtener_pedido(s, datos.numero)]
    else:
        pedidos = sv.listar_pedidos(s)[:50]
    rechazos = sv.rechazos_por_pedido(s)
    compacto = []
    for p in pedidos:
        r = sv.resumen_pedido(p)
        compacto.append(
            {
                "pedido": p.numero,
                "cliente": p.cliente,
                "unidades": p.cantidad,
                "avance_pct": r["avance"],
                "paquetes_por_estado": {NOMBRES[k]: v for k, v in r["conteo"].items()},
                "rechazos": rechazos.get(p.id, 0),
                "creado": p.creado_en.date().isoformat(),
            }
        )
    if not compacto:
        return ResumenIASalida(texto="Todavía no hay pedidos registrados.")
    return ResumenIASalida(texto=ia.resumir(compacto))
