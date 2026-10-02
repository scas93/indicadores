"""Catálogos de planeación (centro gestor → eje → subtema → estrategia) y frecuencias.
Baja lógica: se deshabilita (`activo=false`), nunca se borra, para no romper el histórico."""
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import validators_planeacion as vp
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import CentroGestor, Eje, Estrategia, Frecuencia, Subtema
from .bitacora import registrar


@dataclass(frozen=True)
class Cat:
    modelo: type
    entidad: str
    padre_campo: str | None = None
    padre_modelo: type | None = None


CATALOGOS: dict[str, Cat] = {
    "centros-gestores": Cat(CentroGestor, "centro_gestor"),
    "ejes": Cat(Eje, "eje", "centro_gestor_id", CentroGestor),
    "subtemas": Cat(Subtema, "subtema", "eje_id", Eje),
    "estrategias": Cat(Estrategia, "estrategia", "subtema_id", Subtema),
    "frecuencias": Cat(Frecuencia, "frecuencia"),
}


def a_dict(cat: Cat, o) -> dict:
    d = {"id": o.id, "clave": o.clave, "nombre": o.nombre, "activo": o.activo}
    if cat.padre_campo:
        d[cat.padre_campo] = getattr(o, cat.padre_campo)
    return d


def listar(db: Session, cat: Cat, padre_id: uuid.UUID | None, activo: bool | None, q: str | None) -> list[dict]:
    m = cat.modelo
    stmt = select(m)
    if padre_id and cat.padre_campo:
        stmt = stmt.where(getattr(m, cat.padre_campo) == padre_id)
    if activo is not None:
        stmt = stmt.where(m.activo == activo)  # los selectores piden activo=true
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(m.nombre).like(like) | func.lower(m.clave).like(like))
    return [a_dict(cat, o) for o in db.scalars(stmt.order_by(m.clave)).all()]


def _padre_activo(db: Session, cat: Cat, padre_id) -> None:
    padre = db.get(cat.padre_modelo, padre_id) if padre_id else None
    campo = cat.padre_campo
    if padre is None:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Padre inexistente o de otro municipio", {campo: "Inválido"})
    if not padre.activo:
        raise ApiError(422, "JERARQUIA_INVALIDA", "El padre está deshabilitado", {campo: "Deshabilitado"})


def _clave_libre(db: Session, cat: Cat, clave: str, padre_id, excepto: uuid.UUID | None) -> None:
    stmt = select(cat.modelo.id).where(cat.modelo.clave == clave)
    if cat.padre_campo:
        stmt = stmt.where(getattr(cat.modelo, cat.padre_campo) == padre_id)
    if excepto:
        stmt = stmt.where(cat.modelo.id != excepto)
    if db.scalar(stmt) is not None:
        raise ApiError(409, "CLAVE_DUPLICADA", "Ya existe un registro con esa clave",
                       {"clave": "Ya existe"})


def crear(db: Session, actor: ActorCtx, cat: Cat, datos: dict):
    clave, nombre = vp.validar_clave_nombre(datos.get("clave"), datos.get("nombre"))
    padre_id = datos.get(cat.padre_campo) if cat.padre_campo else None
    if cat.padre_campo:
        _padre_activo(db, cat, padre_id)
    _clave_libre(db, cat, clave, padre_id, None)
    o = cat.modelo(municipio_id=actor.municipio_id, clave=clave, nombre=nombre, activo=True,
                   **({cat.padre_campo: padre_id} if cat.padre_campo else {}))
    db.add(o)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CLAVE_DUPLICADA", "Ya existe un registro con esa clave", {"clave": "Ya existe"})
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion=f"{cat.entidad}.crear",
              entidad=cat.entidad, entidad_id=o.id, municipio_id=actor.municipio_id,
              detalle={"clave": clave})
    return o


def editar(db: Session, actor: ActorCtx, cat: Cat, id: uuid.UUID, cambios: dict):
    o = db.get(cat.modelo, id)
    if o is None:
        raise ApiError(404, "NO_ENCONTRADO", "Registro no encontrado")
    clave, nombre = vp.validar_clave_nombre(cambios.get("clave", o.clave), cambios.get("nombre", o.nombre))
    if cat.padre_campo and cambios.get(cat.padre_campo) not in (None, getattr(o, cat.padre_campo)):
        _padre_activo(db, cat, cambios[cat.padre_campo])
        setattr(o, cat.padre_campo, cambios[cat.padre_campo])
    _clave_libre(db, cat, clave, getattr(o, cat.padre_campo) if cat.padre_campo else None, o.id)
    antes = o.activo
    o.clave, o.nombre = clave, nombre
    if cambios.get("activo") is not None:
        o.activo = bool(cambios["activo"])
    accion = f"{cat.entidad}.editar"
    if antes != o.activo:
        accion = f"{cat.entidad}.{'habilitar' if o.activo else 'deshabilitar'}"
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion=accion,
              entidad=cat.entidad, entidad_id=o.id, municipio_id=actor.municipio_id,
              detalle={"clave": o.clave})
    return o
