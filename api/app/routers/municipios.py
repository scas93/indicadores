import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import SesionSuperAdmin, sesion_admin
from ..errors import ApiError
from ..models import ActorTipo, EstadoMunicipio, GeografiaEstado, Municipio, Usuario
from ..schemas import MunicipioCrearIn, MunicipioEditarIn, MunicipioOut
from .. import validators as v
from ..services import municipios as svc
from ..services.bitacora import registrar

router = APIRouter(prefix="/api/admin/municipios", tags=["admin-municipios"])


def _get(db: Session, id: uuid.UUID) -> Municipio:
    m = db.get(Municipio, id)
    if m is None:
        raise ApiError(404, "MUNICIPIO_NO_ENCONTRADO", "Municipio no encontrado")
    return m


@router.get("")
def listar(ses: SesionSuperAdmin = Depends(sesion_admin), db: Session = Depends(get_db)):
    filas = db.execute(
        select(Municipio, GeografiaEstado.nombre)
        .join(GeografiaEstado, GeografiaEstado.id == Municipio.estado_republica_id, isouter=True)
        .order_by(Municipio.created_at.desc())).all()
    return [{**MunicipioOut.model_validate(m).model_dump(), "estado_republica": e}
            for m, e in filas]


@router.get("/subdominio-disponible")
def subdominio_disponible(valor: str, ses: SesionSuperAdmin = Depends(sesion_admin),
                          db: Session = Depends(get_db)):
    """Validación en vivo del modal de alta."""
    try:
        slug = svc.validar_subdominio_db(db, valor)
        return {"disponible": True, "subdominio": slug, "motivo": None}
    except ApiError as e:
        return {"disponible": False, "subdominio": v.normalizar_subdominio(valor),
                "motivo": e.codigo, "mensaje": e.mensaje}


@router.post("", status_code=201)
def crear(body: MunicipioCrearIn, ses: SesionSuperAdmin = Depends(sesion_admin),
          db: Session = Depends(get_db)):
    r = svc.crear_municipio(
        db, actor_id=ses.admin.id, nombre=body.nombre, subdominio=body.subdominio,
        estado_republica_id=body.estado_republica_id, logo_url=body.logo_url,
        admin_nombre=body.admin_nombre, admin_usuario=body.admin_usuario,
        admin_password=body.admin_password)
    return {"municipio": MunicipioOut.model_validate(r["municipio"]),
            "administrador": {"id": r["administrador"].id, "usuario": r["administrador"].usuario,
                              "nombre": r["administrador"].nombre},
            "password_inicial": r["password_inicial"],  # solo si fue generada
            "plantillas_copiadas": r["plantillas_copiadas"]}


@router.get("/{id}")
def detalle(id: uuid.UUID, ses: SesionSuperAdmin = Depends(sesion_admin),
            db: Session = Depends(get_db)):
    m = _get(db, id)
    admins = db.scalars(select(Usuario).where(
        Usuario.municipio_id == m.id, Usuario.tipo == "administrador")).all()
    return {**MunicipioOut.model_validate(m).model_dump(),
            "administradores": [{"id": a.id, "usuario": a.usuario, "nombre": a.nombre,
                                 "activo": a.activo} for a in admins]}


@router.patch("/{id}")
def editar(id: uuid.UUID, body: MunicipioEditarIn, ses: SesionSuperAdmin = Depends(sesion_admin),
           db: Session = Depends(get_db)):
    m = _get(db, id)
    cambios = body.model_dump(exclude_unset=True)
    if "duracion_sesion_dias" in cambios:
        v.validar_duracion_sesion_dias(cambios["duracion_sesion_dias"])
    if "estado_republica_id" in cambios and cambios["estado_republica_id"] and \
            db.get(GeografiaEstado, cambios["estado_republica_id"]) is None:
        raise ApiError(422, "ESTADO_INVALIDO", "Estado inválido", {"estado_republica_id": "No existe"})
    estado_antes = m.estado
    for k, val in cambios.items():
        if k in ("nombre", "estado", "color_boton", "mostrar_logos") and val is None:
            continue
        setattr(m, k, val)
    accion = "municipio.editar"
    if m.estado != estado_antes:
        accion = "municipio.suspender" if m.estado == EstadoMunicipio.suspendido else "municipio.activar"
    registrar(db, actor_tipo=ActorTipo.super_admin, actor_id=ses.admin.id, accion=accion,
              entidad="municipio", entidad_id=m.id, municipio_id=m.id,
              detalle={k: str(val) for k, val in cambios.items()})
    db.commit()
    return MunicipioOut.model_validate(m)
