"""Auth de ámbito municipio: /api/auth/*"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import validators as v
from ..config import Settings, get_settings
from ..db import get_db
from ..deps import COOKIE_MUNICIPIO, SesionUsuario, municipio_actual, sesion_municipio
from ..errors import ApiError
from ..models import Municipio, Sesion, Usuario
from ..schemas import LoginIn, VerificarUsuarioIn
from ..security import passwords_match, sign_session_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _buscar_usuario(db: Session, municipio: Municipio, nombre: str) -> Usuario:
    # `db` ya está aislada por municipio (municipio_actual); el filtro explícito sobra a propósito
    u = db.scalar(select(Usuario).where(Usuario.usuario == nombre.strip()))
    if u is None:
        raise ApiError(404, "USUARIO_NO_EXISTE", "El usuario no existe")
    if not u.activo:
        raise ApiError(403, "USUARIO_INACTIVO", "El usuario está deshabilitado")
    return u


def _branding(m: Municipio) -> dict:
    return {"nombre": m.nombre, "logo_url": m.logo_url, "imagen_login_url": m.imagen_login_url,
            "color_boton": m.color_boton.value, "mostrar_logos": m.mostrar_logos}


@router.get("/branding")
def branding(m: Municipio = Depends(municipio_actual)):
    """Datos de la pantalla de login. Responde 404/403 con código si el municipio no existe o
    está suspendido (el front muestra la página de error, nunca el login)."""
    return _branding(m)


@router.post("/verificar-usuario")
def verificar_usuario(body: VerificarUsuarioIn, m: Municipio = Depends(municipio_actual),
                      db: Session = Depends(get_db)):
    """Paso 1 del login (paridad con el sistema actual: usuario -> 'Iniciado como X' -> password)."""
    u = _buscar_usuario(db, m, body.usuario)
    return {"usuario": u.usuario, "nombre": u.nombre}


@router.post("/login")
def login(body: LoginIn, response: Response, m: Municipio = Depends(municipio_actual),
          db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        u = _buscar_usuario(db, m, body.usuario)
    except ApiError as e:
        if e.codigo == "USUARIO_NO_EXISTE":
            raise ApiError(401, "CREDENCIALES_INVALIDAS", "Usuario o contraseña incorrectos")
        raise
    if not passwords_match(body.password, u.password_encrypted):
        raise ApiError(401, "CREDENCIALES_INVALIDAS", "Usuario o contraseña incorrectos")

    ahora = v.utcnow()
    expira = v.calcular_expiracion(ahora, m.duracion_sesion_dias,
                                   settings.sesion_duracion_minutos_override)
    s = Sesion(usuario_id=u.id, municipio_id=m.id, expires_at=expira)
    db.add(s)
    primera_vez = u.debe_cambiar_password
    u.debe_cambiar_password = False  # spec: se apaga en su primer login exitoso
    db.commit()
    response.set_cookie(
        COOKIE_MUNICIPIO, sign_session_id(s.id), max_age=v.segundos_restantes(expira, ahora),
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return {"usuario": {"id": u.id, "usuario": u.usuario, "nombre": u.nombre,
                        "tipo": u.tipo.value}, "primer_login": primera_vez,
            "expira": expira}


@router.post("/logout")
def logout(response: Response, ses: SesionUsuario = Depends(sesion_municipio),
           db: Session = Depends(get_db)):
    ses.sesion.revoked_at = v.utcnow()
    db.commit()
    response.delete_cookie(COOKIE_MUNICIPIO, path="/")
    return {"ok": True}


@router.get("/me")
def me(ses: SesionUsuario = Depends(sesion_municipio)):
    u = ses.usuario
    return {"usuario": {"id": u.id, "usuario": u.usuario, "nombre": u.nombre, "tipo": u.tipo.value,
                        "debe_cambiar_password": u.debe_cambiar_password},
            "municipio": {"id": ses.municipio.id, **_branding(ses.municipio),
                          "subdominio": ses.municipio.subdominio},
            "expira": ses.sesion.expires_at}
