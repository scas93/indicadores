"""Fase 2 — cálculo de cumplimiento y semáforo (casos 1, 2, 6, 7 y bordes). Funciones puras."""
from decimal import Decimal as D

import pytest

from app import calculo as c

# Rangos reales del indicador de Fin de "Fortalecimiento del empleo" (spec Fase 2, caso 2)
VERDE, AMARILLO, ROJO = (D("8.1"), D("10")), (D("6.1"), D("8")), (D("-50"), D("6"))
MESES_SIN_CAPTURA = [(None, None)] * 12


def test_sumatoria_excluye_meses_sin_captura_no_los_cuenta_como_cero():
    assert c.sumatoria([D(1), None, D(2), None]) == 3
    assert c.sumatoria([None, None]) is None  # ni un mes capturado: None, no 0
    assert c.sumatoria([D(0), None]) == 0     # un 0 capturado SÍ es una captura


@pytest.mark.parametrize("algoritmo,a,b,esperado", [
    ("a_sobre_b_pct", D(1), D(4), D(25)),
    ("a_sobre_b_menos1_pct", D(5), D(4), D(25)),
    ("a_sobre_b_menos1_pct", D(3), D(4), D(-25)),
    ("a_sobre_b", D(1), D(4), D("0.25")),
    ("a", D(7), None, D(7)),
    ("a", D(7), D(0), D(7)),  # B no participa
])
def test_cuatro_algoritmos(algoritmo, a, b, esperado):
    assert c.cumplimiento_bruto(algoritmo, a, b) == esperado


@pytest.mark.parametrize("algoritmo", ["a_sobre_b_pct", "a_sobre_b_menos1_pct", "a_sobre_b"])
def test_caso7_division_entre_cero_es_null_y_gris_sin_excepcion(algoritmo):
    r = c.evaluar(algoritmo, [(D(5), D(0)), (D(2), None)], VERDE, AMARILLO, ROJO)
    assert r.cumplimiento is None and r.color == c.GRIS
    assert r.sumatoria_a == 7 and r.sumatoria_b == 0


def test_b_nula_en_todos_los_meses_con_algoritmo_que_divide_es_no_calculable():
    r = c.evaluar("a_sobre_b_pct", [(D(5), None)] * 3, VERDE, AMARILLO, ROJO)
    assert r.sumatoria_b is None and r.cumplimiento is None and r.color == c.GRIS


def test_caso6_sin_meses_capturados_es_gris_nunca_rojo_ni_sin_color():
    for alg in ("a_sobre_b_pct", "a_sobre_b_menos1_pct", "a_sobre_b", "a"):
        r = c.evaluar(alg, MESES_SIN_CAPTURA, VERDE, AMARILLO, ROJO)
        assert r.color == c.GRIS and r.cumplimiento is None, alg
    # incluso con rangos que contendrían el 0
    assert c.evaluar("a", MESES_SIN_CAPTURA, (D(-9), D(9)), (None, None), (None, None)).color == c.GRIS


def test_sin_algoritmo_no_hay_resultado():
    assert c.evaluar(None, [(D(1), D(1))]).color == c.GRIS


def test_solo_a_ignora_b_guardado_de_antes():
    r = c.evaluar("a", [(D(8), D(100)), (D(1), D(100))], VERDE, AMARILLO, ROJO)
    assert r.sumatoria_b is None and r.cumplimiento == D("9.00") and r.color == c.VERDE


# --- caso 1 y 2: paridad ----------------------------------------------------------
def test_caso1_cumplimiento_2024_sintetico_da_1_18():
    """PENDIENTE de verificación con el dato real: los A/B de abajo son SINTÉTICOS (el dato real de
    "Fortalecimiento del empleo" no está disponible); solo prueban que el motor produce 1.18 con
    A/B×100 sobre sumatorias mensuales. Cuando se cargue el dato real se verifica aparte."""
    # 4 meses capturados (A = 3 + 3 + 3 + 2.8 = 11.8, B = 4 × 250 = 1000) y 8 sin captura
    avances = [(D("3"), D("250"))] * 3 + [(D("2.8"), D("250"))] + [(None, None)] * 8
    r = c.evaluar("a_sobre_b_pct", avances, VERDE, AMARILLO, ROJO)
    assert r.cumplimiento == D("1.18")


def test_caso2_color_con_rangos_reales_sintetico():
    """PENDIENTE de verificación contra el sistema de referencia (mismo dato sintético)."""
    r = c.evaluar("a_sobre_b_pct", [(D("11.8"), D("1000"))], VERDE, AMARILLO, ROJO)
    assert r.cumplimiento == D("1.18") and r.color == c.ROJO  # 1.18 ∈ [-50, 6]


@pytest.mark.parametrize("valor,color", [
    ("10", c.VERDE), ("8.1", c.VERDE), ("8", c.AMARILLO), ("6.1", c.AMARILLO),
    ("6", c.ROJO), ("-50", c.ROJO), ("0", c.ROJO),
])
def test_limites_de_rangos_son_inclusivos(valor, color):
    assert c.color_por_rango(D(valor), VERDE, AMARILLO, ROJO) == color


@pytest.mark.parametrize("valor", ["10.01", "-50.01", "8.05"])
def test_fuera_de_los_tres_rangos_es_sin_color_distinto_de_gris(valor):
    # 8.05 cae en el hueco entre amarillo (hasta 8) y verde (desde 8.1)
    assert c.color_por_rango(D(valor), VERDE, AMARILLO, ROJO) == c.SIN_COLOR != c.GRIS


def test_hay_resultado_pero_fuera_de_rangos_es_sin_color_no_gris():
    r = c.evaluar("a", [(D("50"), None)], VERDE, AMARILLO, ROJO)
    assert r.cumplimiento == D("50.00") and r.color == c.SIN_COLOR


def test_rangos_sin_configurar_dan_sin_color_si_hay_resultado():
    assert c.evaluar("a", [(D(1), None)]).color == c.SIN_COLOR


def test_el_color_se_decide_sobre_el_valor_redondeado_que_ve_el_usuario():
    # 8.0999.. se muestra como 8.10 -> verde
    r = c.evaluar("a_sobre_b", [(D("8.0999"), D(1))], VERDE, AMARILLO, ROJO)
    assert r.cumplimiento == D("8.10") and r.color == c.VERDE


def test_rangos_de_dict_y_objeto():
    d = {"rango_verde_desde": 1, "rango_verde_hasta": 2, "rango_amarillo_desde": None,
         "rango_amarillo_hasta": None, "rango_rojo_desde": 3, "rango_rojo_hasta": 4}
    assert c.rangos_de(d) == ((1, 2), (None, None), (3, 4))
