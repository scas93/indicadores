"""Usuarios: endpoints de municipio (administrador) y espejo del super admin sobre cualquier
municipio. Un solo lugar de lógica (services/usuarios.py); aquí solo se cablea la dependencia."""
import uuid
from typing import Callable

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import validators_usuarios as vu
from ..db import get_db
from ..deps import ActorCtx, actor_admin_en_municipio, actor_con_tipo
from ..schemas import UsuarioCrearIn, UsuarioEditarIn, UsuariosBulkIn
from ..services import usuarios as svc


def _montar(router: APIRouter, dep_ver: Callable, dep_gestion: Callable) -> None:
    @router.get("")
    def listar(tipo: str | None = None, activo: bool | None = None, q: str | None = None,
               actor: ActorCtx = Depends(dep_ver), db: Session = Depends(get_db)):
        return svc.listar(db, tipo, activo, q)

    @router.post("", status_code=201)
    def crear(body: UsuarioCrearIn, actor: ActorCtx = Depends(dep_gestion), db: Session = Depends(get_db)):
        u, generada = svc.crear(db, actor, body.model_dump())
        db.commit()
        return {**svc.a_dict(u, programa_ids=svc.programas_de(db, u.id)), "password_generada": generada}

    if router.prefix == "/api/usuarios":  # alta masiva: solo ámbito municipio
        @router.post("/bulk")
        def bulk(body: UsuariosBulkIn, actor: ActorCtx = Depends(dep_gestion), db: Session = Depends(get_db)):
            r = svc.crear_masivo(db, actor, body.filas)
            db.commit()
            return r

    @router.get("/{id}")
    def detalle(id: uuid.UUID, actor: ActorCtx = Depends(dep_gestion), db: Session = Depends(get_db)):
        u = svc.obtener(db, id)
        password = svc.ver_password(db, actor, u)  # cada consulta queda en bitácora
        db.commit()
        return {**svc.a_dict(u, programa_ids=svc.programas_de(db, u.id)), "password": password}

    @router.patch("/{id}")
    def editar(id: uuid.UUID, body: UsuarioEditarIn, actor: ActorCtx = Depends(dep_gestion),
               db: Session = Depends(get_db)):
        u = svc.editar(db, actor, svc.obtener(db, id), body.model_dump(exclude_unset=True))
        db.commit()
        return svc.a_dict(u, programa_ids=svc.programas_de(db, u.id))

    @router.post("/{id}/forzar-password")
    def forzar(id: uuid.UUID, actor: ActorCtx = Depends(dep_gestion), db: Session = Depends(get_db)):
        nueva = svc.forzar_password(db, actor, svc.obtener(db, id))
        db.commit()
        return {"password": nueva}  # se muestra una sola vez


# /api/usuarios (municipio). main.py incluye la matriz ANTES para que "/matriz" no caiga en "/{id}".
router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])
_montar(router, actor_con_tipo("usuarios_ver"), actor_con_tipo("usuarios_gestion"))

# /api/admin/municipios/{municipio_id}/usuarios (super admin): sin restricción de tipo
admin_router = APIRouter(prefix="/api/admin/municipios/{municipio_id}/usuarios", tags=["admin-usuarios"])
_montar(admin_router, actor_admin_en_municipio, actor_admin_en_municipio)
