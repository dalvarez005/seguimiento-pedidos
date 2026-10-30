"""Casos de uso. Orquestan dominio y BD dentro de una transacción."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import domain
from .models import EventoPaquete, Paquete, Pedido, ahora
from .schemas import PedidoCrear


class NoEncontrado(Exception):
    pass


class Conflicto(Exception):
    pass


def clave(numero: str) -> str:
    """RF-04: comparación sin espacios alrededor y sin distinguir mayúsculas."""
    return numero.strip().upper()


def crear_pedido(s: Session, datos: PedidoCrear) -> Pedido:
    k = clave(datos.numero)
    if s.scalar(select(Pedido.id).where(Pedido.numero_clave == k)) is not None:
        raise Conflicto(f"Ya existe un pedido con el número {datos.numero}.")

    pedido = Pedido(
        numero=datos.numero, numero_clave=k, cliente=datos.cliente, cantidad=datos.cantidad
    )
    pedido.paquetes = [
        Paquete(indice=i, unidades=u, estado="pendiente")
        for i, u in enumerate(domain.dividir_en_paquetes(datos.cantidad), start=1)
    ]
    s.add(pedido)
    try:
        s.commit()
    except IntegrityError:
        # Dos altas simultáneas con el mismo número: decide el UNIQUE de la BD.
        s.rollback()
        raise Conflicto(f"Ya existe un pedido con el número {datos.numero}.") from None
    return pedido


def listar_pedidos(s: Session) -> list[Pedido]:
    return list(s.scalars(select(Pedido).order_by(Pedido.creado_en.desc(), Pedido.id.desc())))


def obtener_pedido(s: Session, numero: str) -> Pedido:
    pedido = s.scalar(select(Pedido).where(Pedido.numero_clave == clave(numero)))
    if pedido is None:
        raise NoEncontrado(f"No existe el pedido {numero}.")
    return pedido


def resumen_pedido(pedido: Pedido) -> dict:
    return domain.resumen((p.unidades, p.estado) for p in pedido.paquetes)


def rechazos_por_pedido(s: Session) -> dict[int, int]:
    filas = s.execute(
        select(Paquete.pedido_id, func.count(EventoPaquete.id))
        .join(EventoPaquete, EventoPaquete.paquete_id == Paquete.id)
        .where(EventoPaquete.accion == "rechazar")
        .group_by(Paquete.pedido_id)
    )
    return {pid: n for pid, n in filas}


def _paquete_bloqueado(s: Session, paquete_id: int) -> Paquete:
    # RNF-03: bloqueo de fila para que dos clics no salten un estado.
    paquete = s.scalar(select(Paquete).where(Paquete.id == paquete_id).with_for_update())
    if paquete is None:
        raise NoEncontrado(f"No existe el paquete {paquete_id}.")
    return paquete


def _mover(s: Session, paquete: Paquete, accion: str, destino: str, motivo=None) -> Paquete:
    s.add(
        EventoPaquete(
            paquete_id=paquete.id,
            accion=accion,
            estado_origen=paquete.estado,
            estado_destino=destino,
            motivo=motivo or None,
        )
    )
    paquete.estado = destino
    paquete.actualizado_en = ahora()
    s.commit()
    s.refresh(paquete.pedido)
    return paquete


def avanzar(s: Session, paquete_id: int) -> Paquete:
    paquete = _paquete_bloqueado(s, paquete_id)
    try:
        destino = domain.siguiente_estado(paquete.estado)
    except domain.TransicionInvalida as e:
        s.rollback()
        raise Conflicto(str(e)) from None
    return _mover(s, paquete, "avanzar", destino)


def rechazar(s: Session, paquete_id: int, motivo: str | None = None) -> Paquete:
    paquete = _paquete_bloqueado(s, paquete_id)
    try:
        destino = domain.estado_tras_rechazo(paquete.estado)
    except domain.TransicionInvalida as e:
        s.rollback()
        raise Conflicto(str(e)) from None
    return _mover(s, paquete, "rechazar", destino, motivo)


def historial(s: Session, paquete_id: int) -> list[EventoPaquete]:
    paquete = s.get(Paquete, paquete_id)
    if paquete is None:
        raise NoEncontrado(f"No existe el paquete {paquete_id}.")
    return list(paquete.eventos)
