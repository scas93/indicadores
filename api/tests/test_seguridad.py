import base64
import uuid

import pytest
from cryptography.exceptions import InvalidTag

from app import security as sec
from app.config import get_settings


def test_password_de_usuario_es_reversible():
    """Caso 7: el cifrado se puede desencriptar de vuelta al valor original."""
    token = sec.encrypt_password("Contraseña con ñ y símbolos !·$")
    assert sec.decrypt_password(token) == "Contraseña con ñ y símbolos !·$"
    assert "Contraseña" not in token


def test_cifrado_usa_nonce_distinto_cada_vez():
    assert sec.encrypt_password("x") != sec.encrypt_password("x")


def test_passwords_match():
    t = sec.encrypt_password("abc")
    assert sec.passwords_match("abc", t)
    assert not sec.passwords_match("abd", t)
    assert not sec.passwords_match("abc", "basura-no-base64")


def test_sin_reglas_de_complejidad_acepta_password_de_un_caracter():
    t = sec.encrypt_password("1")
    assert sec.passwords_match("1", t)


def test_token_alterado_no_descifra():
    blob = bytearray(base64.b64decode(sec.encrypt_password("secreto")))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        sec.decrypt_password(base64.b64encode(bytes(blob)).decode())


def test_password_de_super_admin_es_hash_irreversible():
    h = sec.hash_admin_password("super-secreta")
    assert h.startswith("$argon2")
    assert "super-secreta" not in h
    assert sec.verify_admin_password("super-secreta", h)
    assert not sec.verify_admin_password("otra", h)
    assert not sec.verify_admin_password("x", "no-es-un-hash")
    with pytest.raises(Exception):  # no existe camino de vuelta
        sec.decrypt_password(h)


def test_los_dos_esquemas_no_son_intercambiables():
    reversible = sec.encrypt_password("pw")
    assert not sec.verify_admin_password("pw", reversible)
    assert not sec.passwords_match("pw", sec.hash_admin_password("pw"))


def test_cookie_firmada_ida_y_vuelta_y_alteraciones():
    sid = uuid.uuid4()
    c = sec.sign_session_id(sid)
    assert sec.unsign_session_id(c) == sid
    assert sec.unsign_session_id(c[:-2] + "xx") is None
    assert sec.unsign_session_id(f"{uuid.uuid4()}.{c.split('.')[1]}") is None
    assert sec.unsign_session_id(str(sid)) is None
    assert sec.unsign_session_id(None) is None


def test_cookie_firmada_con_otro_secreto_no_vale(monkeypatch):
    c = sec.sign_session_id(uuid.uuid4())
    monkeypatch.setenv("SESSION_SECRET", "otro")
    get_settings.cache_clear()
    try:
        assert sec.unsign_session_id(c) is None
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
