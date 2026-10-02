import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..schemas import CausaIn, EfectoIn, EncabezadoIn
from ..services import arbol as svc

router = APIRouter(prefix="/api", tags=["arbol"])
_inicio = actor_con_tipo("inicio")


@router.get("/programas/{id}/arbol")
def obtener(id: uuid.UUID, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    return svc.obtener(db, actor, id)


@router.put("/programas/{id}/arbol/encabezado")
def encabezado(id: uuid.UUID, body: EncabezadoIn, actor: ActorCtx = Depends(_inicio),
               db: Session = Depends(get_db)):
    r = svc.editar_encabezado(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.post("/programas/{id}/arbol/causas", status_code=201)
def crear_causa(id: uuid.UUID, body: CausaIn, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    r = svc.crear(db, actor, id, "causa", body.model_dump())
    db.commit()
    return r


@router.patch("/arbol-causa-medio/{id}")
def editar_causa(id: uuid.UUID, body: CausaIn, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    r = svc.editar(db, actor, "causa", id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.delete("/arbol-causa-medio/{id}")
def eliminar_causa(id: uuid.UUID, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    n = svc.eliminar(db, actor, "causa", id)
    db.commit()
    return {"eliminados": n}


@router.post("/programas/{id}/arbol/efectos", status_code=201)
def crear_efecto(id: uuid.UUID, body: EfectoIn, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    r = svc.crear(db, actor, id, "efecto", body.model_dump())
    db.commit()
    return r


@router.patch("/arbol-efecto-fin/{id}")
def editar_efecto(id: uuid.UUID, body: EfectoIn, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    r = svc.editar(db, actor, "efecto", id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.delete("/arbol-efecto-fin/{id}")
def eliminar_efecto(id: uuid.UUID, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    n = svc.eliminar(db, actor, "efecto", id)
    db.commit()
    return {"eliminados": n}
