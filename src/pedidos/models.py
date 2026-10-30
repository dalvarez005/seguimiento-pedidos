"""Tablas (ver plan.md, "Modelo de datos")."""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def ahora() -> datetime:
    return datetime.now(UTC)


class Pedido(Base):
    __tablename__ = "pedidos"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_pedido_cantidad"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(40))
    # RF-04: clave normalizada (sin espacios y en mayúsculas) con UNIQUE.
    numero_clave: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    cliente: Mapped[str] = mapped_column(String(120))
    cantidad: Mapped[int] = mapped_column(Integer)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    paquetes: Mapped[list["Paquete"]] = relationship(
        back_populates="pedido",
        order_by="Paquete.indice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Paquete(Base):
    __tablename__ = "paquetes"
    __table_args__ = (
        UniqueConstraint("pedido_id", "indice", name="uq_paquete_indice"),
        CheckConstraint("unidades BETWEEN 1 AND 100", name="ck_paquete_unidades"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"))
    indice: Mapped[int] = mapped_column(Integer)
    unidades: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora
    )

    pedido: Mapped[Pedido] = relationship(back_populates="paquetes")
    eventos: Mapped[list["EventoPaquete"]] = relationship(
        back_populates="paquete",
        order_by="EventoPaquete.id",
        cascade="all, delete-orphan",
    )


class EventoPaquete(Base):
    """RF-09: historial de avances y rechazos."""

    __tablename__ = "eventos_paquete"

    id: Mapped[int] = mapped_column(primary_key=True)
    paquete_id: Mapped[int] = mapped_column(
        ForeignKey("paquetes.id", ondelete="CASCADE"), index=True
    )
    accion: Mapped[str] = mapped_column(String(10))  # avanzar | rechazar
    estado_origen: Mapped[str] = mapped_column(String(20))
    estado_destino: Mapped[str] = mapped_column(String(20))
    motivo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    paquete: Mapped[Paquete] = relationship(back_populates="eventos")
