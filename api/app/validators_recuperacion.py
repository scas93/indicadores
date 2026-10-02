"""Reglas de la recuperación de contraseña por email (funciones puras)."""
import hashlib
from datetime import datetime, timedelta

from .errors import ApiError

VIGENCIA_TOKEN = timedelta(hours=1)


def hash_token(token: str) -> str:
    """El token solo viaja en el link del correo; en la base solo vive su hash."""
    return hashlib.sha256(token.encode()).hexdigest()


def expiracion_token(ahora: datetime) -> datetime:
    return ahora + VIGENCIA_TOKEN


def validar_token(expires_at: datetime | None, used_at: datetime | None, ahora: datetime) -> None:
    """Códigos distintos para que el front avise si el token ya se usó o ya venció."""
    if expires_at is None:
        raise ApiError(400, "TOKEN_INVALIDO", "El enlace no es válido")
    if used_at is not None:
        raise ApiError(400, "TOKEN_USADO", "Este enlace ya se utilizó")
    if expires_at <= ahora:
        raise ApiError(400, "TOKEN_VENCIDO", "Este enlace venció, solicita uno nuevo")
