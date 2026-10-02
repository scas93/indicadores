import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..schemas import MatrizGuardarIn
from ..services import matriz as svc

router = APIRouter(prefix="/api/usuarios/matriz", tags=["matriz"])
_gestion = actor_con_tipo("usuarios_gestion")


@router.get("")
def obtener(ejercicio: int, centro_gestor_id: uuid.UUID | None = None, tipo: str | None = None,
            q: str | None = None, actor: ActorCtx = Depends(_gestion), db: Session = Depends(get_db)):
    return svc.obtener(db, ejercicio, centro_gestor_id, tipo, q)


@router.post("")
def guardar(body: MatrizGuardarIn, actor: ActorCtx = Depends(_gestion), db: Session = Depends(get_db)):
    r = svc.guardar(db, actor, [(p.usuario_id, p.programa_id) for p in body.altas],
                    [(p.usuario_id, p.programa_id) for p in body.bajas])
    db.commit()  # una sola transacción: si algo falló arriba no se guardó nada
    return r
