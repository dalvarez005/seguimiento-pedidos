import os

import pytest
from sqlalchemy import create_engine
from fastapi.testclient import TestClient

from pedidos.ai import AsistenteIA
from pedidos.app import create_app
from pedidos.config import Settings


@pytest.fixture
def db_url(tmp_path):
    """SQLite temporal, o PostgreSQL si se define TEST_DATABASE_URL (CI)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        yield f"sqlite:///{tmp_path / 'pruebas.db'}"
        return
    yield url
    from pedidos.db import Base

    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def crear_cliente(db_url):
    """Crea un TestClient contra una BD SQLite temporal (se puede reabrir)."""
    abiertos = []

    def _crear(ia: AsistenteIA | None = None) -> TestClient:
        app = create_app(
            Settings(database_url=db_url, anthropic_api_key="", gemini_api_key=""),
            ia=ia or AsistenteIA([]),
        )
        c = TestClient(app)
        c.__enter__()
        abiertos.append(c)
        return c

    yield _crear
    for c in abiertos:
        c.__exit__(None, None, None)


@pytest.fixture
def client(crear_cliente):
    return crear_cliente()


@pytest.fixture
def nuevo_pedido(client):
    def _crear(numero="PED-1", cliente="Ferretería López", cantidad=250):
        r = client.post("/api/pedidos", json={"numero": numero, "cliente": cliente, "cantidad": cantidad})
        assert r.status_code == 201, r.text
        return r.json()

    return _crear
