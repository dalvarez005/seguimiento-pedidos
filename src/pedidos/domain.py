"""Reglas de negocio puras (spec 001). No dependen de la BD ni de HTTP."""

from collections.abc import Iterable

TAMANO_PAQUETE = 100
ESTADOS = ("pendiente", "en_proceso", "revision", "listo")
NOMBRES = {
    "pendiente": "Pendiente",
    "en_proceso": "En proceso",
    "revision": "Revisión",
    "listo": "Listo",
}


class TransicionInvalida(Exception):
    """El paquete no puede pasar al estado pedido (RF-05, RF-06)."""


def dividir_en_paquetes(cantidad: int) -> list[int]:
    """RF-02: paquetes de 100 y uno final con el residuo. 250 -> [100, 100, 50]."""
    # bool es subclase de int: se excluye a propósito.
    if not isinstance(cantidad, int) or isinstance(cantidad, bool):
        raise ValueError("La cantidad debe ser un número entero.")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    completos, resto = divmod(cantidad, TAMANO_PAQUETE)
    return [TAMANO_PAQUETE] * completos + ([resto] if resto else [])


def siguiente_estado(estado: str) -> str:
    """RF-05: solo se avanza al estado inmediato siguiente."""
    if estado not in ESTADOS:
        raise TransicionInvalida(f"Estado desconocido: {estado}.")
    i = ESTADOS.index(estado)
    if i == len(ESTADOS) - 1:
        raise TransicionInvalida("El paquete ya está Listo y no puede avanzar más.")
    return ESTADOS[i + 1]


def estado_tras_rechazo(estado: str) -> str:
    """RF-06: un paquete en Revisión rechazado vuelve a En proceso."""
    if estado != "revision":
        nombre = NOMBRES.get(estado, estado)
        raise TransicionInvalida(
            f"Solo se puede rechazar un paquete en Revisión (está en {nombre})."
        )
    return "en_proceso"


def resumen(paquetes: Iterable[tuple[int, str]]) -> dict:
    """RF-07: conteo por estado y avance por unidades listas.

    `paquetes` es una secuencia de (unidades, estado).
    """
    conteo = dict.fromkeys(ESTADOS, 0)
    total = listas = n = 0
    for unidades, estado in paquetes:
        conteo[estado] += 1
        total += unidades
        n += 1
        if estado == "listo":
            listas += unidades
    avance = round(listas * 100 / total, 1) if total else 0.0
    return {
        "conteo": conteo,
        "total_paquetes": n,
        "unidades_totales": total,
        "unidades_listas": listas,
        "avance": avance,
    }
