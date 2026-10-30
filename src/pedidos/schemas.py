"""Contrato de la API (Pydantic estricto, RF-01 y RF-03)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


LIMITE_UNIDADES = 100_000

Texto40 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Texto120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PedidoCrear(BaseModel):
    numero: Texto40
    cliente: Texto120
    # strict: rechaza "10", 2.5 y true; solo enteros JSON.
    cantidad: int = Field(strict=True, gt=0, le=LIMITE_UNIDADES)


class RechazoEntrada(BaseModel):
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class Resumen(BaseModel):
    conteo: dict[str, int]
    total_paquetes: int
    unidades_totales: int
    unidades_listas: int
    avance: float


class PaqueteSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indice: int
    unidades: int
    estado: str
    actualizado_en: datetime


class PedidoSalida(BaseModel):
    id: int
    numero: str
    cliente: str
    cantidad: int
    creado_en: datetime
    resumen: Resumen
    rechazos: int = 0


class PedidoDetalle(PedidoSalida):
    paquetes: list[PaqueteSalida]


class MovimientoSalida(BaseModel):
    paquete: PaqueteSalida
    pedido: PedidoSalida


class EventoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    accion: str
    estado_origen: str
    estado_destino: str
    motivo: str | None
    creado_en: datetime


# --- IA ---
class InterpretarEntrada(BaseModel):
    texto: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class Borrador(BaseModel):
    numero: str | None = None
    cliente: str | None = None
    cantidad: int | None = None
    faltantes: list[str] = []
    nota: str | None = None


class ResumenIAEntrada(BaseModel):
    numero: str | None = None


class ResumenIASalida(BaseModel):
    texto: str
    modelo: str | None = None  # qué modelo generó el texto (RF-13)


class EstadoIA(BaseModel):
    disponible: bool
    modelo: str | None = None
    proveedores: list[str] = []
