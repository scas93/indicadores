"""Fase 5, parte 1 — reglas de negocio de los catálogos del Padrón (funciones puras)."""
import uuid

import pytest

from app import validators_padron as vp
from app import validators_usuarios as vu
from app.errors import ApiError

A, B, C = (uuid.uuid4() for _ in range(3))


def codigo(fn, *a, **kw):
    with pytest.raises(ApiError) as e:
        fn(*a, **kw)
    return e.value.status, e.value.codigo


# --- quién usa los catálogos -----------------------------------------------------------------------
def test_catalogos_del_padron_solo_padron_y_administrador():
    assert {t for t in ("informes", "padron", "administrador") if vu.tipo_permitido("padron_catalogos", t)} == {
        "padron", "administrador"}
    assert not vu.tipo_permitido("padron_catalogos", None)  # el super admin tiene otro ámbito
    assert codigo(vu.validar_tipo_permitido, "padron_catalogos", "informes") == (403, "TIPO_NO_PERMITIDO")


# --- unicidad de claves -----------------------------------------------------------------------------
def test_clave_repetida_ignora_mayusculas_y_espacios():
    assert vp.clave_repetida(" a-1 ", ["A-1", "B"])
    assert not vp.clave_repetida("A-2", ["A-1", "B"])
    assert codigo(vp.levantar_si_clave_repetida, "x", ["X"]) == (409, "CLAVE_DUPLICADA")
    vp.levantar_si_clave_repetida("x", [])


def test_clave_automatica_de_nivel_y_de_rango_sigue_la_convencion_de_la_plantilla():
    assert vp.clave_desde_nombre("Muy bajo") == "muy_bajo"
    assert vp.clave_desde_nombre("  Nivel Único ") == "nivel_unico"
    assert vp.clave_de_rango(0, 11) == "0-11" and vp.clave_de_rango(60, None) == "60+"


# --- rangos de grupo de edad --------------------------------------------------------------------------
def test_rango_valido_y_abierto():
    assert vp.validar_rango_edad(18, 59) == (18, 59)
    assert vp.validar_rango_edad(60, None) == (60, None)
    assert vp.validar_rango_edad(5, "") == (5, None)


@pytest.mark.parametrize("mn,mx,campo", [(30, 18, "edad_max"), (None, 10, "edad_min"), (-1, 5, "edad_min"),
                                         (0, 999, "edad_max"), ("a", 5, "edad_min"), (True, 5, "edad_min")])
def test_rango_invertido_o_invalido_se_rechaza(mn, mx, campo):
    with pytest.raises(ApiError) as e:
        vp.validar_rango_edad(mn, mx)
    assert (e.value.status, e.value.codigo) == (422, "RANGO_INVALIDO") and campo in e.value.campos


def test_rangos_que_se_traslapan():
    assert vp.rangos_traslapan((0, 11), (11, 17))      # comparten la edad 11
    assert vp.rangos_traslapan((18, 59), (30, 40))     # uno contiene al otro
    assert vp.rangos_traslapan((60, None), (80, 90))   # abierto hacia arriba
    assert vp.rangos_traslapan((60, None), (10, None))
    assert not vp.rangos_traslapan((0, 11), (12, 17))  # contiguos no se traslapan
    assert not vp.rangos_traslapan((60, None), (0, 59))


def test_nuevo_rango_contra_los_existentes():
    existentes = [(A, 0, 11), (B, 12, 17), (C, 60, None)]
    vp.validar_sin_traslape((18, 59), existentes)  # hueco libre: se puede agregar
    assert codigo(vp.validar_sin_traslape, (10, 13), existentes) == (409, "RANGO_TRASLAPADO")
    assert codigo(vp.validar_sin_traslape, (70, 75), existentes) == (409, "RANGO_TRASLAPADO")


def test_al_editar_un_grupo_no_se_compara_contra_si_mismo():
    existentes = [(A, 0, 11), (B, 12, 17)]
    vp.validar_sin_traslape((0, 13 - 2), existentes, excepto=A)  # mismo rango que ya tenía
    assert codigo(vp.validar_sin_traslape, (0, 13), existentes, excepto=A) == (409, "RANGO_TRASLAPADO")


# --- pertenencia entre catálogos --------------------------------------------------------------------
def test_apoyo_solo_a_un_programa_asignado_activo_y_existente():
    vp.validar_programa_asignado(True, True, frozenset({A}), A)
    vp.validar_programa_asignado(True, True, None, A)  # administrador: todos
    assert codigo(vp.validar_programa_asignado, True, True, frozenset({B}), A) == (422, "PROGRAMA_NO_ASIGNADO")
    assert codigo(vp.validar_programa_asignado, True, True, frozenset(), A) == (422, "PROGRAMA_NO_ASIGNADO")
    assert codigo(vp.validar_programa_asignado, False, False, None, A) == (422, "JERARQUIA_INVALIDA")
    assert codigo(vp.validar_programa_asignado, True, True, None, None) == (422, "JERARQUIA_INVALIDA")
    assert codigo(vp.validar_programa_asignado, True, False, None, A) == (422, "JERARQUIA_INVALIDA")


def test_descripcion_solo_a_un_apoyo_existente_y_visible():
    vp.validar_apoyo_existente(True, True, A)
    assert codigo(vp.validar_apoyo_existente, False, False, A) == (422, "JERARQUIA_INVALIDA")
    assert codigo(vp.validar_apoyo_existente, True, False, A) == (422, "JERARQUIA_INVALIDA")
    assert codigo(vp.validar_apoyo_existente, True, True, None) == (422, "JERARQUIA_INVALIDA")


def test_colonia_el_municipio_debe_ser_del_estado():
    vp.validar_municipio_de_estado(A, A, True)
    assert codigo(vp.validar_municipio_de_estado, A, B, True) == (422, "JERARQUIA_INVALIDA")
    assert codigo(vp.validar_municipio_de_estado, A, None, True) == (422, "JERARQUIA_INVALIDA")
    assert codigo(vp.validar_municipio_de_estado, None, A, False) == (422, "JERARQUIA_INVALIDA")


# --- borrado ------------------------------------------------------------------------------------------
def test_solo_se_borra_si_nada_lo_usa():
    vp.validar_borrable({})
    vp.validar_borrable({"descripciones de apoyo": 0, "entregas": 0})
    with pytest.raises(ApiError) as e:
        vp.validar_borrable({"descripciones de apoyo": 0, "entregas": 3})
    assert (e.value.status, e.value.codigo) == (409, "REGISTRO_EN_USO") and "3 entregas" in e.value.mensaje


def test_ids_unicos_conserva_el_orden():
    assert vp.ids_unicos([B, A, B, C, A]) == [B, A, C]
