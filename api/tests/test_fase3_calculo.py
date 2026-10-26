"""Fase 3 — Estadísticas: reglas de cálculo puras (sin base de datos ni API).
Los casos 4 y 5 (estructura exacta de columnas de las exportaciones) son verificación manual contra el
sistema de referencia; aquí solo hay un humo de que existen y tienen 38 / 26 columnas.

Datos reales: los 19 indicadores del programa 1014 (ECONÓMICO) 2025 salen del export de Cuenta Pública
del sistema de referencia (A/B mensuales, resultado alcanzado y avance/programado). Los rangos de color
NO vienen en el export (solo los del 410): son INFERIDOS para reproducir los conteos verificados en vivo
— RANGOS INFERIDOS, PENDIENTES DE VERIFICACIÓN."""
from decimal import Decimal

import pytest

from app import calculo
from app import calculo_estadisticas as ce

D = Decimal
R410 = {"verde": {"desde": 8.1, "hasta": 10}, "amarillo": {"desde": 6.1, "hasta": 8},
        "rojo": {"desde": -50, "hasta": 6}}

# (id de referencia, algoritmo, meta A programada, meta B programada, A mensual, B mensual,
#  color esperado en modo obtenido, color esperado en C.O/C.E, alcanzada, avance/programado)
REF_2025 = [
    ("411", "a_sobre_b_pct", 15, 100, [3411, 345, 1212, 1032, 345, 673, 523, 345, 345, 641, 456, 250],
     [10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000], "rojo", "rojo", 7.98, 53.2),
    ("410", "a_sobre_b_menos1_pct", 110, 100, [110, 150, 90, 250, 250, 38, 250, 142, 265, 35, 45, 125],
     [100, 80, 70, 250, 222, 25, 210, 189, 240, 40, 45, 120], "verde", "gris", 9.99, 99.9),
    ("512", "a", 4000, None, [120, 120, 200, 120, 110, 100, 140, 200, 100, 100, 625, 205],
     [None, None, None, None, None, None, None, None, None, None, None, None], "gris", "rojo", 2140.0, 53.5),
    ("513", "a", 500, None, [40, 40, 40, 40, 40, 40, 50, 40, 40, 45, 45, 40],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "verde", 500.0, 100.0),
    ("514", "a", 1, None, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [None, None, None, None, None, None, None, None, None, None, None, None], "verde", "verde", 1.0, 100.0),
    ("582", "a", 40, None, [10, 0, 0, 10, 0, 0, 10, 0, 0, 10, 0, 0],
     [None, None, None, None, None, None, None, None, None, None, None, None], "verde", "verde", 40.0, 100.0),
    ("584", "a", 1500, None, [200, 200, 0, 200, 200, 0, 0, 200, 200, 0, 200, 100],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "verde", 1500.0, 100.0),
    ("515", "a", 10, None, [1, 5, 7, 2, 2, 2, 0, 1, 1, None, 3, None],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "verde", 24.0, 240.0),
    ("574", "a", 6, None, [1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 2],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "verde", 8.0, 133.33),
    ("575", "a", 8, None, [2, 2, 0, 2, 0, 0, 1, 2, 1, 0, 0, 0],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "verde", 10.0, 125.0),
    ("576", "a_sobre_b_pct", 80, 100, [200, 521, 200, 120, 254, 326, 250, 320, 405, 254, 120, 350],
     [9000, None, None, None, None, None, None, None, None, None, None, None], "rojo", "rojo", 36.89, 46.11),
    ("577", "a", 1, None, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [None, None, None, None, None, None, None, None, None, None, None, None], "verde", "verde", 1.0, 100.0),
    ("516", "a", 100, None, [25, 4, 3, 25, 2, 7, 25, 6, 5, 25, 0, 0],
     [None, None, None, None, None, None, None, None, None, None, None, None], "verde", "verde", 127.0, 127.0),
    ("517", "a", 540, None, [25, 25, 25, 25, 25, 25, 25, 25, 25, 25, None, 25],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "rojo", 275.0, 50.93),
    ("578", "a", 6, None, [2, 0, 1, 1, 2, 1, 0, 1, 2, 0, 1, 0],
     [None, None, None, None, None, None, None, None, None, None, None, None], "rojo", "verde", 11.0, 183.33),
    ("579", "a_sobre_b_pct", 80, 100, [12, 10, 8, 9, 7, 5, 8, 9, 6, 2, 5, 3],
     [12, 11, 10, 9, 7, 5, 8, 9, 9, 2, 5, 3], "rojo", "verde", 93.33, 116.66),
    ("583", "a", 80, None, [5, 2, 6, 5, 12, 12, 12, 12, 4, 4, 4, 2],
     [None, None, None, None, None, None, None, None, None, None, None, None], "verde", "verde", 80.0, 100.0),
    ("585", "a", 395, None, [39, 42, 25, 28, 32, 25, 45, 20, 20, 22, 49, 31],
     [None, None, None, None, None, None, None, None, None, None, None, None], "verde", "verde", 378.0, 95.7),
    ("586", "a", 35, None, [6, 6, 6, None, None, None, 6, 6, None, None, 4, None],
     [None, None, None, None, None, None, None, None, None, None, None, None], "amarillo", "verde", 34.0, 97.14),
]


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
