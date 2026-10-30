"""Pruebas de la API contra SQLite temporal (RF-01..RF-09)."""

import pytest


def avanzar(client, paquete_id):
    return client.post(f"/api/paquetes/{paquete_id}/avanzar")


def rechazar(client, paquete_id, motivo=None):
    body = {"motivo": motivo} if motivo is not None else None
    return client.post(f"/api/paquetes/{paquete_id}/rechazar", json=body)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_interfaz_se_sirve(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# RF-01 / RF-02
def test_rf01_rf02_crear_pedido_lo_divide_en_paquetes(client):
    r = client.post("/api/pedidos", json={"numero": "PED-1001", "cliente": "Acme", "cantidad": 250})
    assert r.status_code == 201
    p = r.json()
    assert p["numero"] == "PED-1001"
    assert [x["unidades"] for x in p["paquetes"]] == [100, 100, 50]
    assert [x["indice"] for x in p["paquetes"]] == [1, 2, 3]
    assert {x["estado"] for x in p["paquetes"]} == {"pendiente"}
    assert p["resumen"]["conteo"] == {"pendiente": 3, "en_proceso": 0, "revision": 0, "listo": 0}
    assert p["resumen"]["avance"] == 0.0


def test_rf01_recorta_espacios(client):
    r = client.post("/api/pedidos", json={"numero": "  A-1 ", "cliente": " Acme ", "cantidad": 5})
    assert r.status_code == 201
    assert (r.json()["numero"], r.json()["cliente"]) == ("A-1", "Acme")


@pytest.mark.parametrize(
    "body",
    [
        {"numero": "", "cliente": "Acme", "cantidad": 1},
        {"numero": "   ", "cliente": "Acme", "cantidad": 1},
        {"numero": "X", "cliente": "", "cantidad": 1},
        {"numero": "X" * 41, "cliente": "Acme", "cantidad": 1},
        {"cliente": "Acme", "cantidad": 1},
    ],
)
def test_rf01_campos_de_texto_obligatorios(client, body):
    r = client.post("/api/pedidos", json=body)
    assert r.status_code == 422
    assert r.json()["detail"]


# RF-03
@pytest.mark.parametrize("cantidad", [0, -1, -250, 2.5, 100.0, "10", "abc", True, None, [], 100_001])
def test_rf03_cantidad_debe_ser_entero_mayor_que_cero(client, cantidad):
    r = client.post("/api/pedidos", json={"numero": "X-1", "cliente": "Acme", "cantidad": cantidad})
    assert r.status_code == 422, cantidad
    assert "Cantidad" in r.json()["detail"]
    assert client.get("/api/pedidos").json() == []


def test_rf03_mensaje_en_espanol(client):
    r = client.post("/api/pedidos", json={"numero": "X-1", "cliente": "Acme", "cantidad": 0})
    assert r.json()["detail"] == "Cantidad: debe ser mayor que cero."


# RF-04
def test_rf04_numero_no_se_repite(client, nuevo_pedido):
    nuevo_pedido(numero="PED-7")
    r = client.post("/api/pedidos", json={"numero": "PED-7", "cliente": "Otro", "cantidad": 3})
    assert r.status_code == 409
    assert "PED-7" in r.json()["detail"]
    assert len(client.get("/api/pedidos").json()) == 1


@pytest.mark.parametrize("variante", ["ped-7", " PED-7 ", "Ped-7"])
def test_rf04_duplicado_sin_importar_mayusculas_ni_espacios(client, nuevo_pedido, variante):
    nuevo_pedido(numero="PED-7")
    r = client.post("/api/pedidos", json={"numero": variante, "cliente": "Otro", "cantidad": 3})
    assert r.status_code == 409


# RF-05
def test_rf05_flujo_completo_sin_saltos(client, nuevo_pedido):
    paq = nuevo_pedido(cantidad=50)["paquetes"][0]
    estados = [avanzar(client, paq["id"]).json()["paquete"]["estado"] for _ in range(3)]
    assert estados == ["en_proceso", "revision", "listo"]
    r = avanzar(client, paq["id"])
    assert r.status_code == 409
    assert "Listo" in r.json()["detail"]


def test_rf05_avanzar_un_paquete_no_afecta_a_los_demas(client, nuevo_pedido):
    p = nuevo_pedido(cantidad=250)
    avanzar(client, p["paquetes"][0]["id"])
    d = client.get("/api/pedidos/PED-1").json()
    assert [x["estado"] for x in d["paquetes"]] == ["en_proceso", "pendiente", "pendiente"]


def test_rf05_paquete_inexistente(client):
    assert avanzar(client, 9999).status_code == 404


# RF-06
def test_rf06_rechazo_en_revision_vuelve_a_en_proceso(client, nuevo_pedido):
    paq = nuevo_pedido(cantidad=10)["paquetes"][0]
    avanzar(client, paq["id"])
    avanzar(client, paq["id"])
    r = rechazar(client, paq["id"], "Etiquetas mal impresas")
    assert r.status_code == 200
    assert r.json()["paquete"]["estado"] == "en_proceso"
    assert r.json()["pedido"]["rechazos"] == 1
    # puede volver a revisión y terminar
    assert avanzar(client, paq["id"]).json()["paquete"]["estado"] == "revision"
    assert avanzar(client, paq["id"]).json()["paquete"]["estado"] == "listo"


@pytest.mark.parametrize("pasos", [0, 1, 3])  # pendiente, en proceso, listo
def test_rf06_solo_se_rechaza_en_revision(client, nuevo_pedido, pasos):
    paq = nuevo_pedido(cantidad=10)["paquetes"][0]
    for _ in range(pasos):
        avanzar(client, paq["id"])
    r = rechazar(client, paq["id"])
    assert r.status_code == 409
    assert "Revisión" in r.json()["detail"]


def test_rf06_motivo_largo_se_rechaza(client, nuevo_pedido):
    paq = nuevo_pedido(cantidad=10)["paquetes"][0]
    avanzar(client, paq["id"])
    avanzar(client, paq["id"])
    assert rechazar(client, paq["id"], "x" * 301).status_code == 422


# RF-07
def test_rf07_avance_por_unidades_listas(client, nuevo_pedido):
    p = nuevo_pedido(cantidad=250)
    ultimo = p["paquetes"][2]  # 50 unidades
    for _ in range(3):
        r = avanzar(client, ultimo["id"])
    resumen = r.json()["pedido"]["resumen"]
    assert resumen["avance"] == 20.0
    assert resumen["conteo"] == {"pendiente": 2, "en_proceso": 0, "revision": 0, "listo": 1}

    lista = client.get("/api/pedidos").json()
    assert lista[0]["resumen"]["avance"] == 20.0


def test_rf07_pedido_completo_llega_a_100(client, nuevo_pedido):
    p = nuevo_pedido(cantidad=201)
    for paq in p["paquetes"]:
        for _ in range(3):
            avanzar(client, paq["id"])
    d = client.get("/api/pedidos/PED-1").json()
    assert d["resumen"]["avance"] == 100.0
    assert d["resumen"]["conteo"]["listo"] == 3


def test_detalle_busca_sin_distinguir_mayusculas(client, nuevo_pedido):
    nuevo_pedido(numero="PED-AB")
    assert client.get("/api/pedidos/ped-ab").status_code == 200
    assert client.get("/api/pedidos/NO-EXISTE").status_code == 404


# RF-08
def test_rf08_los_datos_persisten_al_reiniciar(crear_cliente):
    c1 = crear_cliente()
    p = c1.post("/api/pedidos", json={"numero": "P-9", "cliente": "Acme", "cantidad": 120}).json()
    c1.post(f"/api/paquetes/{p['paquetes'][0]['id']}/avanzar")
    c1.__exit__(None, None, None)

    c2 = crear_cliente()  # nueva app, misma base de datos
    d = c2.get("/api/pedidos/P-9").json()
    assert [x["estado"] for x in d["paquetes"]] == ["en_proceso", "pendiente"]


# RF-09
def test_rf09_historial_de_movimientos(client, nuevo_pedido):
    paq = nuevo_pedido(cantidad=10)["paquetes"][0]
    avanzar(client, paq["id"])
    avanzar(client, paq["id"])
    rechazar(client, paq["id"], "Falta sello")
    eventos = client.get(f"/api/paquetes/{paq['id']}/historial").json()
    assert [(e["accion"], e["estado_origen"], e["estado_destino"]) for e in eventos] == [
        ("avanzar", "pendiente", "en_proceso"),
        ("avanzar", "en_proceso", "revision"),
        ("rechazar", "revision", "en_proceso"),
    ]
    assert eventos[2]["motivo"] == "Falta sello"


def test_rf09_transicion_invalida_no_deja_evento(client, nuevo_pedido):
    paq = nuevo_pedido(cantidad=10)["paquetes"][0]
    rechazar(client, paq["id"])
    assert client.get(f"/api/paquetes/{paq['id']}/historial").json() == []


# RNF-03: clics simultáneos no saltan estados (bloqueo de fila; solo PostgreSQL)
def test_rnf03_avances_simultaneos_no_saltan_estados(client, nuevo_pedido, db_url):
    if not db_url.startswith("postgresql"):
        pytest.skip("requiere PostgreSQL (TEST_DATABASE_URL)")
    from concurrent.futures import ThreadPoolExecutor

    paq = nuevo_pedido(cantidad=10)["paquetes"][0]
    with ThreadPoolExecutor(max_workers=8) as ex:
        codigos = list(ex.map(lambda _: avanzar(client, paq["id"]).status_code, range(8)))
    assert codigos.count(200) == 3
    assert codigos.count(409) == 5
    eventos = client.get(f"/api/paquetes/{paq['id']}/historial").json()
    assert [e["estado_destino"] for e in eventos] == ["en_proceso", "revision", "listo"]
