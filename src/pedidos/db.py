"""Motor y sesiones de SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def crear_motor(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        # SQLite no aplica claves foráneas si no se le pide.
        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=2)


class Database:
    def __init__(self, url: str):
        self.engine = crear_motor(url)
        self.sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def crear_tablas(self) -> None:
        from . import models  # noqa: F401  (registra las tablas)

        Base.metadata.create_all(self.engine)

    def sesion(self) -> Iterator[Session]:
        with self.sessionmaker() as s:
            yield s
