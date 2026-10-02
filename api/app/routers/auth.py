"""Auth de ámbito municipio: /api/auth/*"""
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import validators as v
from .. import validators_recuperacion as vr
from ..config import Settings, get_settings
from ..db import get_db
from ..deps import COOKIE_MUNICIPIO, SesionUsuario, municipio_actual, sesion_municipio
from ..errors import ApiError
from ..models import ActorTipo, Municipio, PasswordResetToken, Sesion, Usuario
from ..schemas import (CambiarPasswordIn, LoginIn, RecuperarConfirmarIn, RecuperarIn,
                       VerificarUsuarioIn)
from ..security import encrypt_password, passwords_match, sign_session_id
from ..services import email as correo
from ..services.bitacora import registrar
from ..services.usuarios import revocar_sesiones

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
    db.commit()  # debe_cambiar_password es solo informativo: el login no lo toca ni lo exige
    response.set_cookie(
        COOKIE_MUNICIPIO, sign_session_id(s.id), max_age=v.segundos_restantes(expira, ahora),
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return {"usuario": {"id": u.id, "usuario": u.usuario, "nombre": u.nombre,
                        "tipo": u.tipo.value,
                        "debe_cambiar_password": u.debe_cambiar_password}, "expira": expira}


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


@router.post("/cambiar-password")
def cambiar_password(body: CambiarPasswordIn, ses: SesionUsuario = Depends(sesion_municipio),
                     db: Session = Depends(get_db)):
    """Cambio voluntario (nunca obligatorio). Apaga la bandera informativa."""
    u = ses.usuario
    if not passwords_match(body.password_actual, u.password_encrypted):
        raise ApiError(403, "PASSWORD_ACTUAL_INCORRECTA", "La contraseña actual no es correcta",
                       {"password_actual": "Incorrecta"})
    u.password_encrypted = encrypt_password(body.password_nueva)
    u.debe_cambiar_password = False
    revocar_sesiones(db, u.id, excepto=ses.sesion.id)  # las demás sesiones abiertas se cierran
    registrar(db, actor_tipo=ActorTipo.usuario, actor_id=u.id, accion="usuario.cambiar_password",
              entidad="usuario", entidad_id=u.id, municipio_id=ses.municipio.id)
    db.commit()
    return {"ok": True}


@router.post("/recuperar")
def recuperar(body: RecuperarIn, tareas: BackgroundTasks, m: Municipio = Depends(municipio_actual),
              db: Session = Depends(get_db), mailer: correo.Mailer = Depends(correo.get_mailer),
              settings: Settings = Depends(get_settings)):
    """Responde 200 SIEMPRE (exista o no el usuario, tenga o no email) para no revelar qué usuarios
    existen; el correo sale en segundo plano para no filtrar nada por el tiempo de respuesta."""
    u = db.scalar(select(Usuario).where(Usuario.usuario == body.usuario.strip()))
    if u is not None and u.activo and u.email:
        ahora = v.utcnow()
        token = secrets.token_urlsafe(32)
        db.execute(update(PasswordResetToken).where(
            PasswordResetToken.usuario_id == u.id, PasswordResetToken.used_at.is_(None)
        ).values(used_at=ahora))  # un solo enlace vigente por usuario
        db.add(PasswordResetToken(usuario_id=u.id, municipio_id=m.id, token_hash=vr.hash_token(token),
                                  expires_at=vr.expiracion_token(ahora)))
        registrar(db, actor_tipo=ActorTipo.usuario, actor_id=u.id, accion="usuario.recuperar_solicitud",
                  entidad="usuario", entidad_id=u.id, municipio_id=m.id)
        db.commit()
        asunto, html = correo.cuerpo_recuperacion(
            u.nombre, m.nombre, correo.enlace_recuperacion(settings, m.subdominio, token))
        tareas.add_task(mailer.enviar, u.email, asunto, html)
    return {"ok": True}


@router.post("/recuperar/confirmar")
def recuperar_confirmar(body: RecuperarConfirmarIn, m: Municipio = Depends(municipio_actual),
                        db: Session = Depends(get_db)):
    t = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == vr.hash_token(body.token)))
    ahora = v.utcnow()
    vr.validar_token(t.expires_at if t else None, t.used_at if t else None, ahora)
    u = db.get(Usuario, t.usuario_id)
    if u is None or not u.activo:
        raise ApiError(400, "TOKEN_INVALIDO", "El enlace no es válido")
    u.password_encrypted = encrypt_password(body.password_nueva)
    u.debe_cambiar_password = False
    t.used_at = ahora
    revocar_sesiones(db, u.id)
    registrar(db, actor_tipo=ActorTipo.usuario, actor_id=u.id, accion="usuario.recuperar_confirmar",
              entidad="usuario", entidad_id=u.id, municipio_id=m.id)
    db.commit()
    return {"ok": True}
