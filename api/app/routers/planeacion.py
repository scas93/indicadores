import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..models import ClasificacionProgramatica
from ..schemas import CatalogoIn, ProgramaDuplicarIn, ProgramaIn
from ..services import planeacion as svc
from ..services import programas as psvc

router = APIRouter(prefix="/api", tags=["planeacion"])
_ver = actor_con_tipo("planeacion_ver")
_editar = actor_con_tipo("planeacion_editar")
_prog_editar = actor_con_tipo("programas_editar")


def _montar_catalogo(ruta: str, cat: svc.Cat) -> None:
    padre = cat.padre_campo

    @router.get(f"/{ruta}", name=f"listar_{ruta}")
    def listar(activo: bool | None = None, q: str | None = None, padre_id: uuid.UUID | None = None,
               actor: ActorCtx = Depends(_ver), db: Session = Depends(get_db)):
        return svc.listar(db, cat, padre_id, activo, q)

    @router.post(f"/{ruta}", status_code=201, name=f"crear_{ruta}")
    def crear(body: CatalogoIn, actor: ActorCtx = Depends(_editar), db: Session = Depends(get_db)):
        o = svc.crear(db, actor, cat, body.model_dump())
        db.commit()
        return svc.a_dict(cat, o)

    @router.patch(f"/{ruta}/{{id}}", name=f"editar_{ruta}")
    def editar(id: uuid.UUID, body: CatalogoIn, actor: ActorCtx = Depends(_editar),
               db: Session = Depends(get_db)):
        o = svc.editar(db, actor, cat, id, body.model_dump(exclude_unset=True))
        db.commit()
        return svc.a_dict(cat, o)


for _ruta, _cat in svc.CATALOGOS.items():
    _montar_catalogo(_ruta, _cat)


@router.get("/clasificaciones-programaticas")
def clasificaciones(actor: ActorCtx = Depends(_ver), db: Session = Depends(get_db)):
    """Solo lectura en Fase 1: alimenta el selector de Programas."""
    from sqlalchemy import select
    return [{"id": c.id, "clave": c.clave, "nombre": c.nombre} for c in db.scalars(
        select(ClasificacionProgramatica).where(ClasificacionProgramatica.activo.is_(True))
        .order_by(ClasificacionProgramatica.clave))]


# Programas: ver = cualquiera con acceso a planeación (filtrado por su matriz); editar = admin,
# alcalde y presupuestación.
_prog_ver = actor_con_tipo("planeacion_ver")


@router.get("/programas")
def listar_programas(ejercicio: int | None = None, centro_gestor_id: uuid.UUID | None = None,
                     activo: bool | None = None, q: str | None = None,
                     actor: ActorCtx = Depends(_prog_ver), db: Session = Depends(get_db)):
    return psvc.listar(db, actor, ejercicio, centro_gestor_id, activo, q)


@router.post("/programas", status_code=201)
def crear_programa(body: ProgramaIn, actor: ActorCtx = Depends(_prog_editar), db: Session = Depends(get_db)):
    p = psvc.crear(db, actor, body.model_dump())
    db.commit()
    return psvc.a_dict(p)


@router.patch("/programas/{id}")
def editar_programa(id: uuid.UUID, body: ProgramaIn, actor: ActorCtx = Depends(_prog_editar),
                    db: Session = Depends(get_db)):
    p = psvc.editar(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return psvc.a_dict(p)


@router.post("/programas/{id}/duplicar", status_code=201)
def duplicar_programa(id: uuid.UUID, body: ProgramaDuplicarIn, actor: ActorCtx = Depends(_prog_editar),
                      db: Session = Depends(get_db)):
    p = psvc.duplicar(db, actor, id, body.ejercicio_fiscal, body.clave, body.nombre)
    db.commit()
    return psvc.a_dict(p)
