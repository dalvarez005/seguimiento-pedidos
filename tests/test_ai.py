"""Funciones de IA con clientes simulados (sin red). RF-10..RF-13."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import httpx2
import pytest

from pedidos.ai import (
    AsistenteIA,
    IANoDisponible,
    ProveedorAnthropic,
    ProveedorGemini,
    _Extraccion,
    desde_config,
)
from pedidos.config import Settings


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
    proveedor = ProveedorAnthropic("", "modelo-prueba", cliente=SimpleNamespace(messages=mensajes))
    ia = AsistenteIA([proveedor])
    return ia, mensajes


def extraccion(numero="PED-55", cliente="Acme", cantidad=250, nota=None):
    return _Extraccion(numero=numero, cliente=cliente, cantidad=cantidad, nota=nota)


# RF-12
def test_rf12_sin_clave_la_ia_no_esta_disponible(client):
    estado = client.get("/api/ia/estado").json()
    assert estado == {"disponible": False, "modelo": None, "proveedores": []}
    r = client.post("/api/ia/interpretar", json={"texto": "pedido 1 de Acme, 5 unidades"})
    assert r.status_code == 503
    assert client.post("/api/ia/resumen", json={}).status_code == 503


def test_rf12_con_cliente_esta_disponible(crear_cliente):
    ia, _ = asistente()
    c = crear_cliente(ia)
    estado = c.get("/api/ia/estado").json()
    assert estado == {"disponible": True, "modelo": "modelo-prueba", "proveedores": ["anthropic"]}


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
    assert r.json() == {"texto": "Va al 20 %.", "modelo": "modelo-prueba"}
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


# RF-13: respaldo entre proveedores
class ProveedorFalso:
    def __init__(self, nombre, modelo, falla=False, borrador=None, texto="Informe"):
        self.nombre, self.modelo, self.falla = nombre, modelo, falla
        self.borrador = borrador or extraccion().model_dump()
        self.texto = texto
        self.llamadas = 0

    def _quizas_fallar(self):
        self.llamadas += 1
        if self.falla:
            raise IANoDisponible(f"{self.nombre} caído")

    def interpretar(self, texto):
        self._quizas_fallar()
        return self.borrador

    def resumir(self, contenido):
        self._quizas_fallar()
        return self.texto


def test_rf13_si_gemini_falla_responde_claude(crear_cliente):
    gemini = ProveedorFalso("gemini", "g-1", falla=True)
    claude = ProveedorFalso("anthropic", "c-1", borrador=extraccion(cliente="De Claude").model_dump())
    c = crear_cliente(AsistenteIA([gemini, claude]))
    r = c.post("/api/ia/interpretar", json={"texto": "pedido PED-55 de Acme, 250"})
    assert r.status_code == 200
    assert r.json()["cliente"] == "De Claude"
    assert gemini.llamadas == 1 and claude.llamadas == 1


def test_rf13_resumen_indica_el_modelo_que_respondio(crear_cliente):
    ia = AsistenteIA([ProveedorFalso("gemini", "g-1", falla=True),
                      ProveedorFalso("anthropic", "c-1", texto="Todo bien.")])
    c = crear_cliente(ia)
    c.post("/api/pedidos", json={"numero": "P-1", "cliente": "Acme", "cantidad": 10})
    assert c.post("/api/ia/resumen", json={}).json() == {"texto": "Todo bien.", "modelo": "c-1"}


def test_rf13_si_todos_fallan_responde_503(crear_cliente):
    ia = AsistenteIA([ProveedorFalso("gemini", "g-1", falla=True),
                      ProveedorFalso("anthropic", "c-1", falla=True)])
    c = crear_cliente(ia)
    r = c.post("/api/ia/interpretar", json={"texto": "pedido 1 de Acme 5"})
    assert r.status_code == 503
    assert "Ningún servicio de IA" in r.json()["detail"]


def test_rf13_respeta_el_orden_y_no_llama_al_respaldo_si_no_hace_falta(crear_cliente):
    gemini = ProveedorFalso("gemini", "g-1")
    claude = ProveedorFalso("anthropic", "c-1")
    c = crear_cliente(AsistenteIA([gemini, claude]))
    assert c.post("/api/ia/interpretar", json={"texto": "pedido 1 de Acme 5"}).status_code == 200
    assert (gemini.llamadas, claude.llamadas) == (1, 0)
    estado = c.get("/api/ia/estado").json()
    assert estado["proveedores"] == ["gemini", "anthropic"]
    assert estado["modelo"] == "g-1"


def test_rf13_config_arma_proveedores_segun_orden_y_claves():
    s = Settings(gemini_api_key="g", anthropic_api_key="a",
                 gemini_model="g-1, g-2", ai_model="c-1", ai_order="anthropic,gemini")
    assert [(p.nombre, p.modelo) for p in desde_config(s).proveedores] == [
        ("anthropic", "c-1"), ("gemini", "g-1"), ("gemini", "g-2"),
    ]
    solo_gemini = desde_config(Settings(gemini_api_key="g", anthropic_api_key="", gemini_model="g-1"))
    assert [p.nombre for p in solo_gemini.proveedores] == ["gemini"]
    assert not desde_config(Settings(gemini_api_key="", anthropic_api_key="")).disponible


def _gemini(manejador):
    http = httpx2.Client(transport=httpx2.MockTransport(manejador))
    return ProveedorGemini("clave-g", "gemini-prueba", http=http)


def _respuesta_gemini(texto):
    return httpx2.Response(200, json={"candidates": [{"content": {"parts": [{"text": texto}]}}]})


def test_rf13_gemini_envia_solicitud_correcta_y_parsea_el_borrador():
    vistas = []

    def manejador(req):
        vistas.append(req)
        return _respuesta_gemini(json.dumps(
            {"numero": "PED-9", "cliente": "Acme", "cantidad": 230, "nota": None}))

    borrador = _gemini(manejador).interpretar("pedido PED-9 de Acme, 2 cajas de 100 y 30")
    assert borrador == {"numero": "PED-9", "cliente": "Acme", "cantidad": 230, "nota": None}
    req = vistas[0]
    assert req.url.path == "/v1beta/models/gemini-prueba:generateContent"
    assert req.headers["x-goog-api-key"] == "clave-g"
    cuerpo = json.loads(req.content)
    assert cuerpo["generationConfig"]["responseMimeType"] == "application/json"
    assert "<pedido>" in cuerpo["contents"][0]["parts"][0]["text"]


def test_rf13_gemini_resumen_devuelve_texto():
    assert _gemini(lambda req: _respuesta_gemini("Va bien.")).resumir("{}") == "Va bien."


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx2.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}}),
        httpx2.Response(503, json={"error": {"status": "UNAVAILABLE"}}),
        httpx2.Response(200, json={"candidates": []}),
        _respuesta_gemini("esto no es JSON"),
    ],
)
def test_rf13_errores_de_gemini_se_traducen(respuesta):
    with pytest.raises(IANoDisponible):
        _gemini(lambda req: respuesta).interpretar("pedido 1 de Acme 5")


def test_rf13_gemini_tiempo_agotado():
    def manejador(req):
        raise httpx2.ReadTimeout("lento", request=req)

    with pytest.raises(IANoDisponible, match="tardó"):
        _gemini(manejador).resumir("{}")
