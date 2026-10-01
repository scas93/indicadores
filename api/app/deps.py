"""Dependencias de ámbito: resuelven municipio / sesión y entregan una Session ya aislada."""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import validators as v
from .config import Settings, get_settings
from .db import get_db
from .errors import ApiError
from .models import Municipio, Sesion, SuperAdmin, Usuario
from .security import unsign_session_id
from .tenancy import scope_session

COOKIE_MUNICIPIO = "sesion_municipio"
COOKIE_ADMIN = "sesion_admin"


def get_ambito(
    x_municipio_slug: Annotated[str | None, Header()] = None,
    x_ambito: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> v.AmbitoResuelto:
    """El middleware de Next.js agrega X-Municipio-Slug (subdominio del Host) y marca
    X-Ambito: admin cuando el subdominio es el de super admin."""
    if x_ambito == "admin":
        return v.AmbitoResuelto("admin", None)
    return v.resolver_ambito(x_municipio_slug, settings.super_admin_subdomain)


def municipio_actual(
    ambito: v.AmbitoResuelto = Depends(get_ambito), db: Session = Depends(get_db)
) -> Municipio:
    """Paso 3 de la spec: busca por subdominio, exige activo y aísla la Session."""
    if ambito.ambito != "municipio":
        raise ApiError(403, "AMBITO_INVALIDO", "Este endpoint es de ámbito municipio")
    m = db.scalar(select(Municipio).where(Municipio.subdominio == ambito.slug))
    v.validar_estado_municipio(m is not None, m.estado.value if m else None)
    scope_session(db, m.id)  # desde aquí toda consulta de negocio queda filtrada
    return m


@dataclass
class SesionUsuario:
    sesion: Sesion
    usuario: Usuario
    municipio: Municipio


def _cargar_sesion(db: Session, cookie: str | None) -> Sesion:
    sid = unsign_session_id(cookie)
    if sid is None:
        raise ApiError(401, "SESION_REQUERIDA", "Inicia sesión")
    s = db.get(Sesion, sid)
    if s is None:
        raise ApiError(401, "SESION_REQUERIDA", "Inicia sesión")
    if not v.sesion_vigente(s.revoked_at, s.expires_at, v.utcnow()):
        raise ApiError(401, "SESION_EXPIRADA", "La sesión expiró")
    return s


def sesion_municipio(
    municipio: Municipio = Depends(municipio_actual),
    db: Session = Depends(get_db),
    cookie: Annotated[str | None, Cookie(alias=COOKIE_MUNICIPIO)] = None,
) -> SesionUsuario:
    s = _cargar_sesion(db, cookie)
    v.validar_tipo_sesion(s.usuario_id, s.super_admin_id, "usuario")
    v.validar_municipio_sesion(s.municipio_id, municipio.id)  # paso 4
    u = db.get(Usuario, s.usuario_id)
    if u is None or not u.activo:
        raise ApiError(401, "SESION_INVALIDA", "Usuario inactivo")
    return SesionUsuario(s, u, municipio)


@dataclass
class SesionSuperAdmin:
    sesion: Sesion
    admin: SuperAdmin


def ambito_admin(ambito: v.AmbitoResuelto = Depends(get_ambito)) -> None:
    if ambito.ambito != "admin":
        raise ApiError(403, "AMBITO_INVALIDO", "Este endpoint es de ámbito admin")


def sesion_admin(
    _: None = Depends(ambito_admin),
    db: Session = Depends(get_db),
    cookie: Annotated[str | None, Cookie(alias=COOKIE_ADMIN)] = None,
) -> SesionSuperAdmin:
    s = _cargar_sesion(db, cookie)
    v.validar_tipo_sesion(s.usuario_id, s.super_admin_id, "super_admin")
    a = db.get(SuperAdmin, s.super_admin_id)
    if a is None:
        raise ApiError(401, "SESION_INVALIDA", "Sesión inválida")
    return SesionSuperAdmin(s, a)
