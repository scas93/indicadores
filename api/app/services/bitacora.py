import uuid

from sqlalchemy.orm import Session

from ..models import ActorTipo, Bitacora


def registrar(db: Session, *, actor_tipo: ActorTipo, actor_id: uuid.UUID, accion: str,
              entidad: str, entidad_id: uuid.UUID | None = None,
              municipio_id: uuid.UUID | None = None, detalle: dict | None = None) -> None:
    db.add(Bitacora(municipio_id=municipio_id, actor_tipo=actor_tipo, actor_id=actor_id,
                    accion=accion, entidad=entidad, entidad_id=entidad_id, detalle=detalle or {}))
