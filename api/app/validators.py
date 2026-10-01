"""Reglas de negocio de Fase 0 como funciones puras (sin FastAPI ni base de datos)."""
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal

from .errors import ApiError

SUBDOMINIO_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
RESERVADOS_BASE = frozenset({"admin", "www"})  # siempre reservados, aunque falle el seed


def normalizar_subdominio(valor: str) -> str:
    return (valor or "").strip().lower()


def validar_subdominio(
    valor: str, reservados: Iterable[str] = (), en_uso: Iterable[str] = ()
) -> str:
    """Devuelve el slug normalizado o lanza ApiError (422 formato/reservado, 409 en uso)."""
    slug = normalizar_subdominio(valor)
    if not SUBDOMINIO_RE.match(slug):
        raise ApiError(
            422, "SUBDOMINIO_INVALIDO",
            "Solo minúsculas, números y guiones (1-63 caracteres, sin guion al inicio o fin)",
            {"subdominio": "Formato inválido"},
        )
    if slug in RESERVADOS_BASE or slug in set(reservados):
        raise ApiError(422, "SUBDOMINIO_RESERVADO", "Subdominio reservado",
                       {"subdominio": "Subdominio reservado"})
    if slug in set(en_uso):
        raise ApiError(409, "SUBDOMINIO_EN_USO", "El subdominio ya está en uso",
                       {"subdominio": "Ya está en uso"})
    return slug


# --- resolución de ámbito ----------------------------------------------------
Ambito = Literal["admin", "municipio", "ninguno"]


@dataclass(frozen=True)
class AmbitoResuelto:
    ambito: Ambito
    slug: str | None


def resolver_ambito(slug: str | None, super_admin_subdomain: str = "admin") -> AmbitoResuelto:
    slug = normalizar_subdominio(slug or "")
    if not slug:
        return AmbitoResuelto("ninguno", None)
    if slug == super_admin_subdomain:
        return AmbitoResuelto("admin", None)
    return AmbitoResuelto("municipio", slug)


def validar_estado_municipio(existe: bool, estado: str | None) -> None:
    if not existe:
        raise ApiError(404, "MUNICIPIO_NO_ENCONTRADO", "Municipio no encontrado")
    if estado != "activo":
        raise ApiError(403, "MUNICIPIO_SUSPENDIDO", "Municipio suspendido")


def validar_municipio_sesion(sesion_municipio_id: uuid.UUID | None, actual_id: uuid.UUID) -> None:
    if sesion_municipio_id != actual_id:
        raise ApiError(403, "MUNICIPIO_NO_COINCIDE", "La sesión pertenece a otro municipio")


def validar_tipo_sesion(
    usuario_id: uuid.UUID | None, super_admin_id: uuid.UUID | None, esperado: Literal["usuario", "super_admin"]
) -> None:
    """Una sesión es de usuario o de super admin, nunca ambas ni intercambiables."""
    if (usuario_id is None) == (super_admin_id is None):
        raise ApiError(401, "SESION_INVALIDA", "Sesión inválida")
    es = "usuario" if usuario_id is not None else "super_admin"
    if es != esperado:
        raise ApiError(401, "SESION_INVALIDA", "Sesión inválida para este ámbito")


# --- vigencia de sesión ------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def calcular_expiracion(
    ahora: datetime, dias: int, minutos_override: int | None = None
) -> datetime:
    if minutos_override is not None:
        return ahora + timedelta(minutes=minutos_override)
    return ahora + timedelta(days=dias)


def sesion_vigente(revoked_at: datetime | None, expires_at: datetime, ahora: datetime) -> bool:
    return revoked_at is None and expires_at > ahora


def segundos_restantes(expires_at: datetime, ahora: datetime) -> int:
    return max(0, int((expires_at - ahora).total_seconds()))


def validar_duracion_sesion_dias(valor: int) -> int:
    if not isinstance(valor, int) or valor < 1 or valor > 3650:
        raise ApiError(422, "DURACION_INVALIDA", "La duración debe ser de 1 a 3650 días",
                       {"duracion_sesion_dias": "Debe ser de 1 a 3650"})
    return valor
