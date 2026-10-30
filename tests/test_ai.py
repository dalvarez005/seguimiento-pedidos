"""Funciones de IA con un cliente Anthropic simulado (sin red). RF-10..RF-12."""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from pedidos.ai import AsistenteIA, _Extraccion


class MensajesFalsos:
    def __init__(self, extraccion=None, texto="Informe", error=None, stop="end_turn"):
        self.extraccion = extraccion
        self.texto = texto
        self.error = error
        self.stop = stop
        self.llamadas = []

    def parse(self, **kw):
        self.llamadas.append(("parse", kw))
        if self.error:
            raise self.error
        return SimpleNamespace(stop_reason=self.stop, parsed_output=self.extraccion)

    def create(self, **kw):
        self.llamadas.append(("create", kw))
        if self.error:
            raise self.error
        return SimpleNamespace(
            stop_reason=self.stop, content=[SimpleNamespace(type="text", text=self.texto)]
        )


def asistente(**kw):
    mensajes = MensajesFalsos(**kw)
    ia = AsistenteIA(api_key="", modelo="modelo-prueba", cliente=SimpleNamespace(messages=mensajes))
    return ia, mensajes


def extraccion(numero="PED-55", cliente="Acme", cantidad=250, nota=None):
    return _Extraccion(numero=numero, cliente=cliente, cantidad=cantidad, nota=nota)


# RF-12
def test_rf12_sin_clave_la_ia_no_esta_disponible(client):
    assert client.get("/api/ia/estado").json() == {"disponible": False, "modelo": None}
    r = client.post("/api/ia/interpretar", json={"texto": "pedido 1 de Acme, 5 unidades"})
    assert r.status_code == 503
    assert client.post("/api/ia/resumen", json={}).status_code == 503


def test_rf12_con_cliente_esta_disponible(crear_cliente):
    ia, _ = asistente()
    c = crear_cliente(ia)
    assert c.get("/api/ia/estado").json() == {"disponible": True, "modelo": "modelo-prueba"}


# RF-10
def test_rf10_interpretar_devuelve_borrador_y_no_guarda(crear_cliente):
    ia, msgs = asistente(extraccion=extraccion())
    c = crear_cliente(ia)
    r = c.post("/api/ia/interpretar", json={"texto": "pedido PED-55 para Acme, 250 unidades"})
    assert r.status_code == 200
    assert r.json() == {
        "numero": "PED-55", "cliente": "Acme", "cantidad": 250, "faltantes": [], "nota": None,
    }
    assert c.get("/api/pedidos").json() == []  # la IA no guarda
    _, kw = msgs.llamadas[0]
    assert kw["model"] == "modelo-prueba"
    assert kw["output_format"] is _Extraccion
    assert "<pedido>" in kw["messages"][0]["content"]


def test_rf10_campos_faltantes_o_invalidos_quedan_vacios(crear_cliente):
    ia, _ = asistente(extraccion=extraccion(numero=None, cantidad=-3))
    c = crear_cliente(ia)
    b = c.post("/api/ia/interpretar", json={"texto": "algo para Acme"}).json()
    assert b["numero"] is None and b["cantidad"] is None
    assert b["faltantes"] == ["numero", "cantidad"]
    assert "-3" in b["nota"]


def test_rf10_avisa_si_el_numero_ya_existe(crear_cliente):
    ia, _ = asistente(extraccion=extraccion(numero="ped-1"))
    c = crear_cliente(ia)
    c.post("/api/pedidos", json={"numero": "PED-1", "cliente": "Acme", "cantidad": 5})
    b = c.post("/api/ia/interpretar", json={"texto": "pedido ped-1 de Acme 250"}).json()
    assert "ya existe" in b["nota"]


def test_rf10_texto_muy_corto(crear_cliente):
    ia, _ = asistente(extraccion=extraccion())
    c = crear_cliente(ia)
    assert c.post("/api/ia/interpretar", json={"texto": "a"}).status_code == 422


# RF-11
def test_rf11_resumen_envia_datos_del_pedido(crear_cliente):
    ia, msgs = asistente(texto="Va al 20 %.")
    c = crear_cliente(ia)
    p = c.post("/api/pedidos", json={"numero": "P-1", "cliente": "Acme", "cantidad": 250}).json()
    for _ in range(3):
        c.post(f"/api/paquetes/{p['paquetes'][2]['id']}/avanzar")
    r = c.post("/api/ia/resumen", json={"numero": "P-1"})
    assert r.json() == {"texto": "Va al 20 %."}
    contenido = msgs.llamadas[0][1]["messages"][0]["content"]
    assert '"avance_pct":20.0' in contenido
    assert '"Listo":1' in contenido


def test_rf11_resumen_sin_pedidos_no_llama_a_la_ia(crear_cliente):
    ia, msgs = asistente()
    c = crear_cliente(ia)
    assert "no hay pedidos" in c.post("/api/ia/resumen", json={}).json()["texto"]
    assert msgs.llamadas == []


def test_rf11_resumen_de_pedido_inexistente(crear_cliente):
    ia, _ = asistente()
    c = crear_cliente(ia)
    assert c.post("/api/ia/resumen", json={"numero": "NADA"}).status_code == 404


# Errores del servicio de IA -> 503 con mensaje claro
def _req():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIConnectionError(request=_req()),
        anthropic.RateLimitError("lento", response=httpx.Response(429, request=_req()), body=None),
        anthropic.InternalServerError("x", response=httpx.Response(500, request=_req()), body=None),
    ],
)
def test_errores_de_la_ia_responden_503(crear_cliente, error):
    ia, _ = asistente(error=error)
    c = crear_cliente(ia)
    r = c.post("/api/ia/interpretar", json={"texto": "pedido 1 de Acme 5"})
    assert r.status_code == 503
    assert r.json()["detail"]


def test_rechazo_del_modelo_responde_503(crear_cliente):
    ia, _ = asistente(extraccion=extraccion(), stop="refusal")
    c = crear_cliente(ia)
    assert c.post("/api/ia/interpretar", json={"texto": "pedido 1 de Acme 5"}).status_code == 503
