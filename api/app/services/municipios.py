import secrets
import string
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import validators as v
from ..errors import ApiError
from ..models import (ActorTipo, ColorBoton, GeografiaEstado, Municipio, SubdominioReservado,
                      TipoUsuario, Usuario)
from ..security import encrypt_password
from . import plantillas
from .bitacora import registrar


def generar_password(n: int = 10) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(n))


def validar_subdominio_db(db: Session, valor: str) -> str:
    reservados = db.scalars(select(SubdominioReservado.subdominio)).all()
    slug = v.normalizar_subdominio(valor)
    en_uso = db.scalars(select(Municipio.subdominio).where(Municipio.subdominio == slug)).all()
    return v.validar_subdominio(slug, reservados, en_uso)


def crear_municipio(db: Session, *, actor_id: uuid.UUID, nombre: str, subdominio: str,
                    estado_republica_id: uuid.UUID | None, logo_url: str | None,
                    admin_nombre: str, admin_usuario: str, admin_password: str | None) -> dict:
    """Transacción única: municipio + copia de plantillas + primer Administrador.
    Si cualquier paso falla se hace rollback completo (no queda nada a medias)."""
    try:
        slug = validar_subdominio_db(db, subdominio)
        if estado_republica_id and db.get(GeografiaEstado, estado_republica_id) is None:
            raise ApiError(422, "ESTADO_INVALIDO", "Estado de la república inválido",
                           {"estado_republica_id": "No existe"})
        m = Municipio(id=uuid.uuid4(), nombre=nombre.strip(), subdominio=slug,
                      estado_republica_id=estado_republica_id, logo_url=logo_url,
                      color_boton=ColorBoton.info)
        db.add(m)
        db.flush()  # una violación de unique (carrera) salta aquí
        conteo = plantillas.copiar_plantillas(db, m)
        generada = not admin_password
        password = admin_password or generar_password()
        u = Usuario(id=uuid.uuid4(), municipio_id=m.id, usuario=admin_usuario.strip(),
                    password_encrypted=encrypt_password(password), tipo=TipoUsuario.administrador,
                    nombre=admin_nombre.strip(), activo=True, debe_cambiar_password=True)
        db.add(u)
        registrar(db, actor_tipo=ActorTipo.super_admin, actor_id=actor_id, accion="municipio.crear",
                  entidad="municipio", entidad_id=m.id, municipio_id=m.id,
                  detalle={"subdominio": slug, "plantillas": conteo})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "SUBDOMINIO_EN_USO", "El subdominio ya está en uso",
                       {"subdominio": "Ya está en uso"})
    except Exception:
        db.rollback()
        raise
    return {"municipio": m, "administrador": u,
            "password_inicial": password if generada else None, "plantillas_copiadas": conteo}
