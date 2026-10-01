from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import validators as v
from ..config import Settings, get_settings
from ..db import get_db
from ..deps import COOKIE_ADMIN, SesionSuperAdmin, ambito_admin, sesion_admin
from ..errors import ApiError
from ..models import Sesion, SuperAdmin
from ..schemas import LoginIn
from ..security import sign_session_id, verify_admin_password

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


@router.post("/login")
def login(body: LoginIn, response: Response, _: None = Depends(ambito_admin),
          db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    a = db.scalar(select(SuperAdmin).where(SuperAdmin.usuario == body.usuario.strip()))
    # argon2: comparación de hash, jamás se descifra
    if a is None or not verify_admin_password(body.password, a.password_hash):
        raise ApiError(401, "CREDENCIALES_INVALIDAS", "Usuario o contraseña incorrectos")
    ahora = v.utcnow()
    expira = v.calcular_expiracion(ahora, settings.admin_session_dias,
                                   settings.sesion_duracion_minutos_override)
    s = Sesion(super_admin_id=a.id, municipio_id=None, expires_at=expira)
    db.add(s)
    db.commit()
    response.set_cookie(
        COOKIE_ADMIN, sign_session_id(s.id), max_age=v.segundos_restantes(expira, ahora),
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return {"admin": {"id": a.id, "usuario": a.usuario, "nombre": a.nombre}}


@router.post("/logout")
def logout(response: Response, ses: SesionSuperAdmin = Depends(sesion_admin),
           db: Session = Depends(get_db)):
    ses.sesion.revoked_at = v.utcnow()
    db.commit()
    response.delete_cookie(COOKIE_ADMIN, path="/")
    return {"ok": True}


@router.get("/me")
def me(ses: SesionSuperAdmin = Depends(sesion_admin)):
    a = ses.admin
    return {"admin": {"id": a.id, "usuario": a.usuario, "nombre": a.nombre}}
