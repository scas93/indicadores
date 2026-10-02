"""Fase 2 — validadores puros de la MIR: rangos, metas, niveles únicos, tolerancia (casos 3, 4, 5)."""
from datetime import date
from decimal import Decimal as D

import pytest

from app import validators_mir as v
from app.errors import ApiError


def err(fn, *a, **k) -> ApiError:
    with pytest.raises(ApiError) as e:
        fn(*a, **k)
    return e.value


# --- rangos --------------------------------------------------------------------
def test_rangos_reales_del_ejemplo_son_validos():
    v.validar_rangos((D("8.1"), D(10)), (D("6.1"), D(8)), (D(-50), D(6)))


def test_rangos_no_necesitan_cubrir_todo_el_eje_ni_estar_todos():
    v.validar_rangos((D(8), D(10)), (None, None), (None, None))
    v.validar_rangos((None, None), (None, None), (None, None))


@pytest.mark.parametrize("verde,amarillo,rojo", [
    ((D(5), D(10)), (D(6), D(8)), (None, None)),        # amarillo dentro de verde
    ((D(8), D(10)), (D(6), D(8)), (None, None)),        # se tocan en 8 (intervalos cerrados)
    ((D(8), D(10)), (D(1), D(2)), (D(9), D(20))),       # verde y rojo
])
def test_rangos_que_se_traslapan_se_rechazan(verde, amarillo, rojo):
    assert err(v.validar_rangos, verde, amarillo, rojo).codigo == "RANGOS_INVALIDOS"


def test_rango_incompleto_o_invertido():
    assert "rango_verde" in err(v.validar_rangos, (D(1), None), (None, None), (None, None)).campos
    assert "rango_rojo" in err(v.validar_rangos, (None, None), (None, None), (D(9), D(1))).campos


# --- caso 4: metas sin algoritmo/frecuencia -------------------------------------------
def test_caso4_metas_sin_algoritmo_ni_frecuencia_422_con_lo_que_falta():
    e = err(v.validar_metas_permitidas, None, None)
    assert e.status == 422 and set(e.campos) == {"algoritmo", "frecuencia_id"}
    assert "el algoritmo" in e.mensaje and "la frecuencia" in e.mensaje
    assert set(err(v.validar_metas_permitidas, "a", None).campos) == {"frecuencia_id"}
    assert set(err(v.validar_metas_permitidas, None, "f1").campos) == {"algoritmo"}
    v.validar_metas_permitidas("a", "f1")


def test_metas_anios_repetidos_y_un_solo_ejercicio_fiscal():
    assert err(v.validar_metas_anuales, "a_sobre_b", [{"anio": 2024}, {"anio": 2024}]).codigo == "ANIO_REPETIDO"
    dos = [{"anio": 2024, "es_ejercicio_fiscal": True}, {"anio": 2025, "es_ejercicio_fiscal": True}]
    assert err(v.validar_metas_anuales, "a_sobre_b", dos).codigo == "EJERCICIO_FISCAL_MULTIPLE"
    assert err(v.validar_metas_anuales, "a_sobre_b", [{"anio": 1999}]).codigo == "ANIO_INVALIDO"


# --- caso 3: solo A bloquea B -----------------------------------------------------------
def test_caso3_solo_a_rechaza_b_en_metas_y_avances():
    assert err(v.validar_metas_anuales, "a", [{"anio": 2024, "valor_b_programado": D(1)}]).codigo == "VARIABLE_B_BLOQUEADA"
    v.validar_metas_anuales("a", [{"anio": 2024, "valor_a_programado": D(1), "valor_b_programado": None}])
    e = err(v.validar_avances_b, "a", [{"mes": 1, "valor_a": D(1), "valor_b": D(2)}, {"mes": 2, "valor_b": None}])
    assert e.codigo == "VARIABLE_B_BLOQUEADA" and set(e.campos) == {"mes_1"}
    v.validar_avances_b("a_sobre_b", [{"mes": 1, "valor_b": D(2)}])  # con B habilitada, sin problema
    assert not v.usa_b("a") and v.usa_b("a_sobre_b") and v.usa_b(None)


# --- fin y propósito únicos ---------------------------------------------------------------
def test_fin_y_proposito_unicos_por_programa():
    assert err(v.validar_alta_nivel_unico, "fin", ["fin", "proposito"]).codigo == "NIVEL_UNICO"
    assert err(v.validar_alta_nivel_unico, "proposito", ["fin", "proposito"]).status == 409
    v.validar_alta_nivel_unico("fin", [])
    v.validar_alta_nivel_unico("componente", ["componente", "fin"])  # los demás niveles sí repiten


def test_fin_y_proposito_no_se_eliminan():
    assert err(v.validar_eliminable, "fin").codigo == "NIVEL_NO_ELIMINABLE"
    assert err(v.validar_eliminable, "proposito").codigo == "NIVEL_NO_ELIMINABLE"
    v.validar_eliminable("componente")
    v.validar_eliminable("actividad")


# --- caso 5: meses activos y tolerancia ------------------------------------------------
HOY = date(2026, 10, 3)


def test_lista_vacia_es_automatico_12_meses_activos_sin_tolerancia():
    assert all(v.mes_capturable(2026, m, HOY, [], 0) for m in range(1, 13))
    assert all(v.mes_capturable(2026, m, HOY, [], 30) for m in range(1, 13))


def test_mes_activo_siempre_capturable():
    assert v.mes_capturable(2020, 3, HOY, [3, 6], 0)


def test_caso5_mes_fuera_de_activos_y_de_tolerancia_se_rechaza():
    assert not v.mes_capturable(2026, 2, HOY, [3, 6], 5)   # febrero terminó hace meses
    assert not v.mes_capturable(2026, 9, HOY, [3, 6], 2)   # sept terminó el 30/09; 30/09 + 2 = 02/10 < 03/10


def test_caso5_mes_dentro_de_tolerancia_se_acepta_y_el_limite_es_inclusivo():
    assert v.mes_capturable(2026, 9, HOY, [3, 6], 3)        # 30/09 + 3 = 03/10 == hoy
    assert v.mes_capturable(2026, 9, HOY, [3, 6], 10)
    assert v.mes_capturable(2026, 9, date(2026, 10, 1), [3, 6], 1)


def test_clasificar_meses_rechaza_los_malos_sin_bloquear_el_resto():
    entrantes = [{"mes": 3, "valor_a": D(1), "valor_b": None},   # activo
                 {"mes": 9, "valor_a": D(2), "valor_b": None},   # tolerancia
                 {"mes": 2, "valor_a": D(3), "valor_b": None}]   # fuera
    ok, mal = v.clasificar_meses(2026, entrantes, {}, HOY, [3, 6], 3)
    assert [m["mes"] for m in ok] == [3, 9]
    assert [m.mes for m in mal] == [2] and mal[0].codigo == "MES_NO_CAPTURABLE"


def test_mes_bloqueado_sin_cambios_no_cuenta_como_rechazo():
    # el front manda los 12 meses; los bloqueados vienen con el valor ya guardado
    vigentes = {2: (D("3.0"), None)}
    ok, mal = v.clasificar_meses(2026, [{"mes": 2, "valor_a": D("3"), "valor_b": None}], vigentes, HOY, [3], 0)
    assert ok == [] and mal == []
    # cambiarlo sí se rechaza; borrarlo también
    _, mal = v.clasificar_meses(2026, [{"mes": 2, "valor_a": None, "valor_b": None}], vigentes, HOY, [3], 0)
    assert [m.mes for m in mal] == [2]


def test_mes_invalido():
    assert err(v.validar_mes, 13).codigo == "MES_INVALIDO"
    assert err(v.validar_mes, 0).status == 422
