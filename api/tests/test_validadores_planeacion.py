"""Fase 1 — reglas de planeación y programas (funciones puras)."""
import uuid

import pytest

from app import validators_planeacion as vp
from app.errors import ApiError

CG, EJE, ST, ST2, ES = (uuid.uuid4() for _ in range(5))


def test_clave_y_nombre():
    assert vp.validar_clave_nombre(" A1 ", " Salud ") == ("A1", "Salud")
    for c, n in [("", "x"), ("x", ""), (None, None), ("x" * 33, "n")]:
        with pytest.raises(ApiError) as e:
            vp.validar_clave_nombre(c, n)
        assert e.value.status == 422


def test_ejercicio():
    assert vp.validar_ejercicio(2026) == 2026
    for malo in (1999, 2101, True, "2026"):
        with pytest.raises(ApiError):
            vp.validar_ejercicio(malo)


def _ok():
    return (vp.Ref(CG, True), vp.Ref(ST, True, EJE, CG), vp.Ref(ES, True, ST))


def test_jerarquia_valida():
    c, s, e = _ok()
    vp.validar_referencias_programa(c, s, e, True, True)
    vp.validar_referencias_programa(c, None, None)  # subtema y estrategia son opcionales


def test_jerarquia_centro_deshabilitado_o_inexistente():
    with pytest.raises(ApiError):
        vp.validar_referencias_programa(None, None, None)
    with pytest.raises(ApiError) as e:
        vp.validar_referencias_programa(vp.Ref(CG, False), None, None)
    assert e.value.campos["centro_gestor_id"] == "Centro gestor deshabilitado"


def test_jerarquia_subtema_de_otro_centro_gestor():
    c, _, _ = _ok()
    with pytest.raises(ApiError) as e:
        vp.validar_referencias_programa(c, vp.Ref(ST2, True, EJE, uuid.uuid4()), None, True)
    assert "subtema_id" in e.value.campos


def test_jerarquia_estrategia_de_otro_subtema():
    c, s, _ = _ok()
    with pytest.raises(ApiError) as e:
        vp.validar_referencias_programa(c, s, vp.Ref(ES, True, ST2), True, True)
    assert "estrategia_id" in e.value.campos


def test_jerarquia_estrategia_o_subtema_deshabilitados():
    c, s, e = _ok()
    with pytest.raises(ApiError):
        vp.validar_referencias_programa(c, vp.Ref(ST, False, EJE, CG), None, True)
    with pytest.raises(ApiError):
        vp.validar_referencias_programa(c, s, vp.Ref(ES, False, ST), True, True)


# --- caso 8: duplicar --------------------------------------------------------
def test_duplicar_exige_clave_nueva():
    vp.validar_duplicado_programa(2026, "P01", 2027, "P01-B", {"P02"})
    with pytest.raises(ApiError) as e:
        vp.validar_duplicado_programa(2026, "P01", 2027, "P01", set())
    assert e.value.codigo == "CLAVE_REPETIDA"
    with pytest.raises(ApiError) as e:
        vp.validar_duplicado_programa(2026, "P01", 2027, " ", set())
    assert e.value.status == 422


def test_duplicar_clave_ocupada_en_el_destino():
    with pytest.raises(ApiError) as e:
        vp.validar_duplicado_programa(2026, "P01", 2027, "P09", {"P09"})
    assert (e.value.status, e.value.codigo) == (409, "CLAVE_DUPLICADA")


def test_duplicar_ejercicio_destino_valido():
    with pytest.raises(ApiError):
        vp.validar_duplicado_programa(2026, "P01", 1900, "X", set())
