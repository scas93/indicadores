"""Reglas puras de las Estadísticas del Padrón (4.3a)."""
from datetime import date

import pytest

from app import validators_padron_estadisticas as vpe
from app.errors import ApiError


def test_contar_agrupa_lo_que_no_tiene_etiqueta_como_sin_grupo_y_los_totales_cuadran():
    r = vpe.contar(["ADULTO", None, "NIÑO", "ADULTO", "", None, None], vpe.SIN_GRUPO)
    assert r == [("Sin grupo", 4), ("ADULTO", 2), ("NIÑO", 1)]
    assert sum(n for _, n in r) == 7  # nada se pierde: coincide con el total de capturas


def test_contar_empata_por_nombre():
    assert vpe.contar(["b", "a", "b", "a"], "x") == [("a", 2), ("b", 2)]


def test_top_5_de_localidades_y_sin_localidad_no_compite():
    cuentas = vpe.contar(["L1"] * 6 + ["L2"] * 5 + ["L3"] * 4 + ["L4"] * 3 + ["L5"] * 2 + ["L6"] * 1 + [None] * 9, vpe.SIN_LOCALIDAD)
    top = vpe.top_n(cuentas, excluir=[vpe.SIN_LOCALIDAD])
    assert [k for k, _ in top] == ["L1", "L2", "L3", "L4", "L5"] and len(top) == 5
    assert vpe.top_n({"a": 1}, 5) == [("a", 1)]


def test_genero_sobre_el_total_de_apoyos():
    g = vpe.conteo_genero(["F", "F", "M", None])
    assert (g["femenino"], g["masculino"], g["sin_dato"], g["total"]) == (2, 1, 1, 4)
    assert (g["pct_femenino"], g["pct_masculino"]) == (50.0, 25.0)
    assert vpe.conteo_genero([])["pct_femenino"] == 0.0  # sin capturas no divide entre cero


def test_concentrado_exige_curp_y_que_exista():
    for mala in (None, "", "   "):
        with pytest.raises(ApiError) as e:
            vpe.validar_curp_concentrado(mala)
        assert e.value.mensaje == "Para Generar Tipo Concentrado debe tener un CURP valido"
    with pytest.raises(ApiError):
        vpe.validar_curp_concentrado("ABC", existe=False)
    assert vpe.validar_curp_concentrado(" abc1 ", existe=True) == "ABC1"


def test_rangos_de_anios_y_de_fechas():
    assert vpe.validar_rango_anios(None, None, 2026) == (2026, 2026)
    assert vpe.validar_rango_anios(2021, 2026, 2026) == (2021, 2026)
    for ini, fin in ((2020, 2026), (2022, 2027), (2025, 2024)):
        with pytest.raises(ApiError):
            vpe.validar_rango_anios(ini, fin, 2026)
    hoy = date(2026, 11, 4)
    assert vpe.validar_rango_fechas(None, None, hoy) == (hoy, hoy)  # ambas por defecto hoy
    with pytest.raises(ApiError):
        vpe.validar_rango_fechas(date(2026, 11, 5), date(2026, 11, 4), hoy)


def test_etiqueta_de_colonia_catalogo_o_texto_libre():
    assert vpe.etiqueta_colonia("C01", "Jardines", "ignorado") == "[C01]Jardines"
    assert vpe.etiqueta_colonia(None, None, "  Mi colonia ") == "Mi colonia"
    assert vpe.etiqueta_colonia(None, None, None) == ""


def test_comparativo_top_por_total_del_rango_con_todos_los_anios():
    filas = [("A", 2024)] * 1 + [("A", 2025)] * 3 + [("B", 2024)] * 3 + [("C", 2026)] * 2 + [(None, 2025)] * 9
    r = vpe.comparativo_top(filas, [2024, 2025, 2026], n=2)
    assert [x["nombre"] for x in r] == ["A", "B"] and [x["total"] for x in r] == [4, 3]  # A=4 gana a B=3 sumando años
    assert r[0]["anios"] == {2024: 1, 2025: 3, 2026: 0}
    por = vpe.apoyos_por_anio([("x", 2030)], [2024])
    assert por == {"x": {2024: 0}}  # un año fuera del rango no cuenta
