import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..services import estadisticas as svc
from ..services import exportaciones as exp

router = APIRouter(prefix="/api/estadisticas", tags=["estadisticas"])
_amplio = actor_con_tipo("estadisticas_dependencias")  # Dependencias y selectores
_mir = actor_con_tipo("estadisticas")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

Anio = Annotated[int, Query(ge=1900, le=2200)]
Tipo = Annotated[str, Query(description="obtenido | co_ce")]
Ids = Annotated[list[uuid.UUID] | None, Query(alias="centro_gestor_ids[]")]


@router.get("/opciones")
def opciones(actor: ActorCtx = Depends(_amplio), db: Session = Depends(get_db)):
    return svc.opciones(db, actor)


@router.get("/dependencias")
def dependencias(anio: Anio, tipo_cumplimiento: Tipo = "obtenido", centro_gestor_ids: Ids = None,
                 actor: ActorCtx = Depends(_amplio), db: Session = Depends(get_db)):
    return svc.por_dependencia(db, actor, anio, tipo_cumplimiento, centro_gestor_ids)


@router.get("/ejes")
def ejes(anio: Anio, tipo_cumplimiento: Tipo = "obtenido",
         eje_ids: Annotated[list[uuid.UUID] | None, Query(alias="eje_ids[]")] = None,
         actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    return svc.por_eje(db, actor, anio, tipo_cumplimiento, eje_ids)


@router.get("/cumplimiento-metas")
def cumplimiento_metas(anio: Anio, centro_gestor_id: uuid.UUID, tipo_cumplimiento: Tipo = "obtenido",
                       actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    return svc.cumplimiento_metas(db, actor, anio, tipo_cumplimiento, centro_gestor_id)


@router.get("/consolidado")
def consolidado(anio: Anio, tipo_cumplimiento: Tipo = "obtenido", centro_gestor_ids: Ids = None,
                actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    return svc.consolidado(db, actor, anio, tipo_cumplimiento, centro_gestor_ids)


@router.get("/indicadores")
def indicadores(anio: Anio, tipo_cumplimiento: Tipo = "obtenido", centro_gestor_ids: Ids = None,
                eje_id: uuid.UUID | None = None, color: str | None = None,
                actor: ActorCtx = Depends(_amplio), db: Session = Depends(get_db)):
    return svc.detalle(db, actor, anio, tipo_cumplimiento, centro_gestor_ids=centro_gestor_ids,
                       eje_id=eje_id, color=color)


# --- Cuenta Pública y Transparencia: un año, un centro gestor, un programa (selección única) ---
@router.get("/cuenta-publica")
def cuenta_publica(anio: Anio, centro_gestor_id: uuid.UUID, programa_id: uuid.UUID,
                   actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    """Vista previa (botón Buscar): la misma tabla del export."""
    return exp.cuenta_publica(db, actor, anio, centro_gestor_id, programa_id)


@router.get("/exportar/cuenta-publica")
def exportar_cuenta_publica(anio: Anio, centro_gestor_id: uuid.UUID, programa_id: uuid.UUID,
                            actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    t = exp.cuenta_publica(db, actor, anio, centro_gestor_id, programa_id)
    return Response(exp.cuenta_publica_xlsx(t), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{t["nombre_archivo"]}"'})


@router.get("/transparencia")
def transparencia(anio: Anio, centro_gestor_id: uuid.UUID, programa_id: uuid.UUID,
                  actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    return exp.transparencia(db, actor, anio, centro_gestor_id, programa_id)


@router.get("/exportar/transparencia")
def exportar_transparencia(anio: Anio, centro_gestor_id: uuid.UUID, programa_id: uuid.UUID,
                           actor: ActorCtx = Depends(_mir), db: Session = Depends(get_db)):
    t = exp.transparencia(db, actor, anio, centro_gestor_id, programa_id)
    return Response(exp.transparencia_xlsx(t), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{t["nombre_archivo"]}"'})
