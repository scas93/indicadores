"""Fase 3 — Estadísticas: reglas de cálculo puras (sin base de datos ni API).
Los casos 4 y 5 (estructura exacta de columnas de las exportaciones) son verificación manual contra el
sistema de referencia; aquí solo hay un humo de que existen y tienen 38 / 26 columnas.

Datos reales (seed_data/economico_2025.py): los 19 indicadores del programa 1014 (ECONÓMICO) 2025 salen del export de Cuenta Pública
del sistema de referencia (A/B mensuales, resultado alcanzado y avance/programado). Los rangos de color
NO vienen en el export (solo los del 410): son INFERIDOS para reproducir los conteos verificados en vivo
— RANGOS INFERIDOS, PENDIENTES DE VERIFICACIÓN."""
from decimal import Decimal

import pytest

from app import calculo
from app import calculo_estadisticas as ce
from seed_data.economico_2025 import REF_2025

D = Decimal


def test_modo_co_ce_divide_entre_la_meta_y_redondea_a_dos_decimales():
    res = calculo.evaluar("a_sobre_b_pct", [(D(7980), D(100000))], (D(50), D(100)), (D(30), D(50)), (D(0), D(30)))
    assert res.cumplimiento == D("7.98")
    valor, color = ce.valor_y_color(ce.CO_CE, res, D(15), (D(50), D(100)), (D(30), D(50)), (D(0), D(30)))
    assert valor == D("53.20") and color == "verde"  # 7.98 / 15 * 100


def test_fuera_de_los_tres_rangos_es_gris_no_sin_color_en_ambos_modos():
    """Caso real: 410 en 2025, C.O/C.E → 99.90 con rangos 8.1–10 / 6.1–8 / -50–6 → gris."""
    res = calculo.evaluar("a_sobre_b_menos1_pct", [(D(110), D(100))])  # sin rangos: sin_color en Fase 2
    assert res.color == calculo.SIN_COLOR
    assert ce.valor_y_color(ce.OBTENIDO, res, D(10), (None, None), (None, None), (None, None))[1] == "gris"
    res = calculo.evaluar("a", [(D("9.99"), None)], (D("8.1"), D(10)), (D("6.1"), D(8)), (D(-50), D(6)))
    assert res.color == "verde"
    valor, color = ce.valor_y_color(ce.CO_CE, res, D(10), (D("8.1"), D(10)), (D("6.1"), D(8)), (D(-50), D(6)))
    assert (valor, color) == (D("99.90"), "gris")


@pytest.mark.parametrize("meta", [None, D(0)])
def test_co_ce_sin_meta_o_meta_cero_es_gris(meta):
    res = calculo.evaluar("a", [(D(5), None)], (D(0), D(100)), (None, None), (None, None))
    assert ce.valor_y_color(ce.CO_CE, res, meta, (D(0), D(100)), (None, None), (None, None)) == (None, "gris")


def test_sin_resultado_es_gris_y_modo_desconocido_falla():
    res = calculo.evaluar("a_sobre_b_pct", [(D(1), D(0))])  # B = 0
    assert res.color == "gris"
    assert ce.valor_y_color(ce.OBTENIDO, res, D(10), (None, None), (None, None), (None, None))[1] == "gris"
    with pytest.raises(ValueError):
        ce.valor_y_color("otro", res, D(10), (None, None), (None, None), (None, None))


def test_contar_siempre_suma_el_total_y_agrupa_cualquier_otro_color_en_gris():
    c = ce.contar(["verde", "verde", "rojo", "gris", "sin_color"])
    assert c == dict(verde=2, amarillo=0, rojo=1, gris=2, total=5)
    assert c["verde"] + c["amarillo"] + c["rojo"] + c["gris"] == c["total"]
    assert ce.sumar([c, ce.contar(["amarillo"])])["total"] == 6


def test_indicador_con_datos_exige_meta_y_al_menos_una_captura():
    assert ce.indicador_con_datos(D(10), [(None, None), (D(1), None)])
    assert not ce.indicador_con_datos(D(10), [(None, None)])  # meta pero sin capturas (pendiente de verificación)
    assert not ce.indicador_con_datos(None, [(D(1), None)])
    assert not ce.indicador_con_datos(D(10), [])


def test_meta_numerica_aplica_el_algoritmo_a_lo_programado():
    assert ce.meta_numerica("a_sobre_b_pct", D(15), D(100)) == D(15)
    assert ce.meta_numerica("a", D(4000), None) == D(4000)  # el texto de la meta es otro campo
    assert ce.meta_numerica("a_sobre_b_pct", D(15), D(0)) is None


def test_los_datos_de_referencia_son_coherentes_con_el_calculo():
    """Cada fila real reproduce su alcanzada y su avance/programado con el cálculo de Fase 2."""
    for ref, alg, ma, mb, A, B, _o, _c, alc, av in REF_2025:
        res = calculo.evaluar(alg, list(zip(map(_d, A), map(_d, B))))
        assert float(res.cumplimiento) == pytest.approx(alc, abs=0.01), ref
        meta = ce.meta_numerica(alg, _d(ma), _d(mb))
        valor, _ = ce.valor_y_color(ce.CO_CE, res, meta, *calculo.rangos_de({
            f"rango_{c}_{k}": None for c in ("verde", "amarillo", "rojo") for k in ("desde", "hasta")}))
        assert float(valor) == pytest.approx(av, abs=0.01), ref


def _d(x):
    return None if x is None else D(str(x))
