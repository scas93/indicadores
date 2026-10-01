import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import validators as v
from app.errors import ApiError

AHORA = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_resolver_ambito():
    assert v.resolver_ambito("admin") == v.AmbitoResuelto("admin", None)
    assert v.resolver_ambito("Demo") == v.AmbitoResuelto("municipio", "demo")
    assert v.resolver_ambito("") == v.AmbitoResuelto("ninguno", None)
    assert v.resolver_ambito(None) == v.AmbitoResuelto("ninguno", None)
    assert v.resolver_ambito("admin", "panel").ambito == "municipio"


def test_estado_municipio():
    v.validar_estado_municipio(True, "activo")
    with pytest.raises(ApiError) as e:
        v.validar_estado_municipio(False, None)
    assert (e.value.status, e.value.codigo) == (404, "MUNICIPIO_NO_ENCONTRADO")
    with pytest.raises(ApiError) as e:
        v.validar_estado_municipio(True, "suspendido")
    assert (e.value.status, e.value.codigo) == (403, "MUNICIPIO_SUSPENDIDO")


def test_sesion_de_otro_municipio_se_rechaza():
    a, b = uuid.uuid4(), uuid.uuid4()
    v.validar_municipio_sesion(a, a)
    with pytest.raises(ApiError) as e:
        v.validar_municipio_sesion(a, b)
    assert (e.value.status, e.value.codigo) == (403, "MUNICIPIO_NO_COINCIDE")
    with pytest.raises(ApiError):  # sesión de super admin (municipio nulo) en un municipio
        v.validar_municipio_sesion(None, b)


def test_sesion_usuario_y_super_admin_no_son_intercambiables():
    u, s = uuid.uuid4(), uuid.uuid4()
    v.validar_tipo_sesion(u, None, "usuario")
    v.validar_tipo_sesion(None, s, "super_admin")
    with pytest.raises(ApiError):
        v.validar_tipo_sesion(u, None, "super_admin")
    with pytest.raises(ApiError):
        v.validar_tipo_sesion(None, s, "usuario")
    with pytest.raises(ApiError):  # ambos o ninguno: sesión corrupta
        v.validar_tipo_sesion(u, s, "usuario")
    with pytest.raises(ApiError):
        v.validar_tipo_sesion(None, None, "usuario")


def test_expiracion_en_dias_y_override_en_minutos():
    assert v.calcular_expiracion(AHORA, 30) == AHORA + timedelta(days=30)
    assert v.calcular_expiracion(AHORA, 30, minutos_override=2) == AHORA + timedelta(minutes=2)


def test_sesion_vigente():
    exp = AHORA + timedelta(minutes=5)
    assert v.sesion_vigente(None, exp, AHORA)
    assert not v.sesion_vigente(None, exp, exp)  # vence justo en expires_at
    assert not v.sesion_vigente(None, exp, exp + timedelta(seconds=1))
    assert not v.sesion_vigente(AHORA, exp, AHORA)  # revocada


def test_segundos_restantes_nunca_negativo():
    assert v.segundos_restantes(AHORA, AHORA + timedelta(hours=1)) == 0
    assert v.segundos_restantes(AHORA + timedelta(seconds=90), AHORA) == 90


@pytest.mark.parametrize("dias", [0, -1, 3651])
def test_duracion_sesion_fuera_de_rango(dias):
    with pytest.raises(ApiError):
        v.validar_duracion_sesion_dias(dias)


def test_duracion_sesion_valida():
    assert v.validar_duracion_sesion_dias(30) == 30
