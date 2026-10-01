import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import SesionSuperAdmin, sesion_admin
from ..errors import ApiError
from ..models import ActorTipo
from ..schemas import PlantillaIn
from ..services import plantillas as svc
from ..services.bitacora import registrar

router = APIRouter(prefix="/api/admin/plantillas", tags=["admin-plantillas"])

# Editar o borrar una plantilla global NO toca las copias ya hechas en los municipios.


def _out(item, cat: svc.Catalogo) -> dict:
    d = {"id": item.id, "clave": item.clave, "nombre": item.nombre}
    for c in cat.extra:
        d[c] = getattr(item, c)
    return d


def _valor(campo: str, valor):
    """Las columnas *_id llegan como texto: se validan/convierten a UUID (o None)."""
    if campo.endswith("_id") and valor not in (None, ""):
        try:
            return uuid.UUID(str(valor))
        except ValueError:
            raise ApiError(422, "VALIDACION", "Identificador inválido", {campo: "Identificador inválido"})
    return None if (campo.endswith("_id") and valor == "") else valor


def _datos(body: PlantillaIn, cat: svc.Catalogo) -> dict:
    extra = body.model_extra or {}
    datos = {"clave": body.clave.strip(), "nombre": body.nombre.strip()}
    for c in cat.extra:
        if c in extra:
            datos[c] = _valor(c, extra[c])
    return datos


@router.get("/{tipo}")
def listar(tipo: str, nivel: str | None = Query(None), padre_id: uuid.UUID | None = None,
           q: str | None = None, ses: SesionSuperAdmin = Depends(sesion_admin),
           db: Session = Depends(get_db)):
    cat = svc.resolver(tipo, nivel)
    stmt = select(cat.modelo).order_by(cat.modelo.clave)
    if tipo == "conac" and nivel:
        stmt = stmt.where(cat.modelo.nivel == nivel)
    if tipo == "conac" and padre_id:
        stmt = stmt.where(cat.modelo.padre_id == padre_id)
    if tipo == "geografia" and padre_id and nivel == "municipio":
        stmt = stmt.where(cat.modelo.estado_id == padre_id)
    if tipo == "geografia" and padre_id and nivel == "localidad":
        stmt = stmt.where(cat.modelo.municipio_geo_id == padre_id)
    if q:
        stmt = stmt.where(cat.modelo.nombre.ilike(f"%{q}%") | cat.modelo.clave.ilike(f"%{q}%"))
    stmt = stmt.limit(500)  # localidades: nunca devolver el catálogo nacional completo
    return [_out(i, cat) for i in db.scalars(stmt)]


@router.post("/{tipo}", status_code=201)
def crear(tipo: str, body: PlantillaIn, nivel: str | None = None,
          ses: SesionSuperAdmin = Depends(sesion_admin), db: Session = Depends(get_db)):
    cat = svc.resolver(tipo, nivel)
    item = cat.modelo(**_datos(body, cat))
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CLAVE_DUPLICADA", "Ya existe un registro con esa clave",
                       {"clave": "Duplicada"})
    registrar(db, actor_tipo=ActorTipo.super_admin, actor_id=ses.admin.id,
              accion="plantilla.crear", entidad=f"plantilla_{tipo}", entidad_id=item.id)
    db.commit()
    return _out(item, cat)


def _get(db: Session, cat: svc.Catalogo, id: uuid.UUID):
    item = db.get(cat.modelo, id)
    if item is None:
        raise ApiError(404, "REGISTRO_NO_ENCONTRADO", "Registro no encontrado")
    return item


@router.patch("/{tipo}/{id}")
def editar(tipo: str, id: uuid.UUID, body: dict, nivel: str | None = None,
           ses: SesionSuperAdmin = Depends(sesion_admin), db: Session = Depends(get_db)):
    cat = svc.resolver(tipo, nivel)
    item = _get(db, cat, id)
    for campo in ("clave", "nombre", *cat.extra):
        if campo in body:
            setattr(item, campo, _valor(campo, body[campo]))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CLAVE_DUPLICADA", "Ya existe un registro con esa clave",
                       {"clave": "Duplicada"})
    registrar(db, actor_tipo=ActorTipo.super_admin, actor_id=ses.admin.id,
              accion="plantilla.editar", entidad=f"plantilla_{tipo}", entidad_id=item.id)
    db.commit()
    return _out(item, cat)


@router.delete("/{tipo}/{id}", status_code=204)
def borrar(tipo: str, id: uuid.UUID, nivel: str | None = None,
           ses: SesionSuperAdmin = Depends(sesion_admin), db: Session = Depends(get_db)):
    cat = svc.resolver(tipo, nivel)
    item = _get(db, cat, id)
    if svc.en_uso(db, tipo, nivel, item):
        raise ApiError(409, "REGISTRO_EN_USO", "No se puede eliminar: algo lo referencia")
    db.delete(item)
    registrar(db, actor_tipo=ActorTipo.super_admin, actor_id=ses.admin.id,
              accion="plantilla.eliminar", entidad=f"plantilla_{tipo}", entidad_id=id)
    db.commit()
