from datetime import datetime, timedelta, timezone

import pytest

from app import validators_recuperacion as vr
from app.errors import ApiError

AHORA = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def test_hash_no_es_el_token_y_es_estable():
    assert vr.hash_token("abc") != "abc"
    assert vr.hash_token("abc") == vr.hash_token("abc") != vr.hash_token("abd")


def test_vigencia_de_1_hora():
    assert vr.expiracion_token(AHORA) == AHORA + timedelta(hours=1)


def test_token_vigente():
    vr.validar_token(AHORA + timedelta(minutes=59), None, AHORA)


@pytest.mark.parametrize("exp,usado,codigo", [
    (None, None, "TOKEN_INVALIDO"),
    (AHORA - timedelta(seconds=1), None, "TOKEN_VENCIDO"),
    (AHORA, None, "TOKEN_VENCIDO"),
    (AHORA + timedelta(hours=1), AHORA - timedelta(minutes=1), "TOKEN_USADO"),
])
def test_token_invalido_vencido_o_usado(exp, usado, codigo):
    with pytest.raises(ApiError) as e:
        vr.validar_token(exp, usado, AHORA)
    assert (e.value.status, e.value.codigo) == (400, codigo)
