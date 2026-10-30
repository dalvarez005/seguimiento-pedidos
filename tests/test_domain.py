"""Pruebas unitarias de las reglas de negocio (sin BD ni HTTP)."""

import pytest

from pedidos.domain import (
    ESTADOS,
    TAMANO_PAQUETE,
    TransicionInvalida,
    dividir_en_paquetes,
    estado_tras_rechazo,
    resumen,
    siguiente_estado,
)


# RF-02 División automática en paquetes
@pytest.mark.parametrize(
    ("cantidad", "esperado"),
    [
        (250, [100, 100, 50]),
        (100, [100]),
        (1, [1]),
        (99, [99]),
        (101, [100, 1]),
        (1000, [100] * 10),
    ],
)
def test_rf02_divide_en_paquetes_de_hasta_100(cantidad, esperado):
    paquetes = dividir_en_paquetes(cantidad)
    assert paquetes == esperado
    assert sum(paquetes) == cantidad
    assert all(1 <= p <= TAMANO_PAQUETE for p in paquetes)


@pytest.mark.parametrize("cantidad", [0, -5])
def test_rf03_division_rechaza_cantidades_no_positivas(cantidad):
    with pytest.raises(ValueError):
        dividir_en_paquetes(cantidad)


@pytest.mark.parametrize("cantidad", [2.5, "10", True, None])
def test_rf03_division_rechaza_valores_que_no_son_enteros(cantidad):
    with pytest.raises(ValueError):
        dividir_en_paquetes(cantidad)


# RF-05 Avanzar sin saltar ni regresar
def test_rf05_orden_de_estados():
    assert ESTADOS == ("pendiente", "en_proceso", "revision", "listo")


@pytest.mark.parametrize(
    ("actual", "siguiente"),
    [("pendiente", "en_proceso"), ("en_proceso", "revision"), ("revision", "listo")],
)
def test_rf05_avanza_solo_al_estado_siguiente(actual, siguiente):
    assert siguiente_estado(actual) == siguiente


def test_rf05_listo_no_avanza():
    with pytest.raises(TransicionInvalida):
        siguiente_estado("listo")


def test_rf05_estado_desconocido():
    with pytest.raises(TransicionInvalida):
        siguiente_estado("enviado")


# RF-06 Rechazo en revisión
def test_rf06_rechazo_en_revision_regresa_a_en_proceso():
    assert estado_tras_rechazo("revision") == "en_proceso"


@pytest.mark.parametrize("estado", ["pendiente", "en_proceso", "listo"])
def test_rf06_solo_se_rechaza_en_revision(estado):
    with pytest.raises(TransicionInvalida):
        estado_tras_rechazo(estado)


# RF-07 Resumen por pedido
def test_rf07_avance_por_unidades_y_no_por_paquetes():
    # 250 = 100 + 100 + 50; solo el de 50 está listo -> 20 %, no 33.3 %
    paquetes = [(100, "pendiente"), (100, "revision"), (50, "listo")]
    r = resumen(paquetes)
    assert r["avance"] == 20.0
    assert r["unidades_listas"] == 50
    assert r["unidades_totales"] == 250
    assert r["conteo"] == {"pendiente": 1, "en_proceso": 0, "revision": 1, "listo": 1}


def test_rf07_conteo_incluye_estados_en_cero():
    r = resumen([(10, "pendiente")])
    assert set(r["conteo"]) == set(ESTADOS)
    assert r["avance"] == 0.0


def test_rf07_avance_completo_y_redondeo():
    assert resumen([(100, "listo"), (1, "listo")])["avance"] == 100.0
    # 1 de 3 unidades -> 33.333… -> 33.3
    assert resumen([(1, "listo"), (2, "pendiente")])["avance"] == 33.3


def test_rf07_resumen_vacio():
    r = resumen([])
    assert r["avance"] == 0.0
    assert r["total_paquetes"] == 0
