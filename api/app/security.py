"""Dos esquemas de contraseña distintos, a propósito (ver spec, Autenticación y sesión):

* usuarios de municipio  -> AES-256-GCM reversible (el Administrador debe poder verla).
* super admin            -> argon2 (hash irreversible).
"""
import base64
import hashlib
import hmac
import os
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

_ph = PasswordHasher()


def _key() -> bytes:
    raw = get_settings().password_encryption_key
    if not raw:
        raise RuntimeError("PASSWORD_ENCRYPTION_KEY no está configurada")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("PASSWORD_ENCRYPTION_KEY debe ser de 32 bytes en base64")
    return key


def encrypt_password(plain: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plain.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_password(token: str) -> str:
    blob = base64.b64decode(token)
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], None).decode()


def passwords_match(plain: str, token: str) -> bool:
    try:
        stored = decrypt_password(token)
    except Exception:
        return False
    return hmac.compare_digest(stored.encode(), plain.encode())


def hash_admin_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_admin_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


# --- cookie firmada: "<sesion_id>.<hmac>" -----------------------------------
def _sig(value: str) -> str:
    mac = hmac.new(get_settings().session_secret.encode(), value.encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode().rstrip("=")


def sign_session_id(sesion_id: uuid.UUID) -> str:
    v = str(sesion_id)
    return f"{v}.{_sig(v)}"


def unsign_session_id(cookie: str | None) -> uuid.UUID | None:
    if not cookie or "." not in cookie:
        return None
    value, sig = cookie.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sig(value)):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
