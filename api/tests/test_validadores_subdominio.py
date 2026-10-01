import pytest

from app.errors import ApiError
from app.validators import normalizar_subdominio, validar_subdominio


def test_acepta_slug_valido_y_lo_normaliza():
    assert validar_subdominio("  Guadalajara ") == "guadalajara"
    assert validar_subdominio("apaseo-el-alto") == "apaseo-el-alto"
    assert validar_subdominio("a") == "a"
    assert validar_subdominio("m2025") == "m2025"


@pytest.mark.parametrize("malo", ["", "-demo", "demo-", "de mo", "demo.mx", "dé", "a_b", "x" * 64])
def test_rechaza_formato_invalido(malo):
    with pytest.raises(ApiError) as e:
        validar_subdominio(malo)
    assert (e.value.status, e.value.codigo) == (422, "SUBDOMINIO_INVALIDO")


def test_admin_y_www_siempre_reservados_aunque_el_seed_no_corrio():
    for s in ("admin", "ADMIN", "www"):
        with pytest.raises(ApiError) as e:
            validar_subdominio(s, reservados=[])
        assert e.value.codigo == "SUBDOMINIO_RESERVADO"


def test_rechaza_reservados_del_seed():
    with pytest.raises(ApiError) as e:
        validar_subdominio("api", reservados=["api"])
    assert e.value.codigo == "SUBDOMINIO_RESERVADO"


def test_en_uso_responde_409():
    with pytest.raises(ApiError) as e:
        validar_subdominio("demo", en_uso=["demo"])
    assert (e.value.status, e.value.codigo) == (409, "SUBDOMINIO_EN_USO")


def test_normalizar():
    assert normalizar_subdominio(None) == ""
