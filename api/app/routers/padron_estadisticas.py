"""Fase 4.3a — Estadísticas del Padrón. Tipos permitidos: padron y administrador; todo acotado a los programas asignados."""
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..services import padron_catalogos as cat
from ..services import padron_estadisticas as svc

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(prefix="/api/padron/estadisticas", tags=["padron-estadisticas"])
_actor = actor_con_tipo("padron_estadisticas")

Programas = Annotated[list[uuid.UUID] | None, Query(alias="programa_ids[]")]
Id = uuid.UUID | None


def _f(programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id, localidad_id, **extra) -> dict:
    return {"programa_ids": programa_ids, "apoyo_id": apoyo_id, "descripcion_apoyo_id": descripcion_apoyo_id,
            "estado_id": estado_id, "municipio_id": municipio_id, "localidad_id": localidad_id, **extra}


@router.get("/dashboard")
def dashboard(programa_ids: Programas = None, apoyo_id: Id = None, descripcion_apoyo_id: Id = None,
              estado_id: Id = None, municipio_id: Id = None, localidad_id: Id = None,
              fecha_ini: date | None = None, fecha_fin: date | None = None,
              actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return svc.dashboard(cat.Ctx(db, actor), _f(programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id,
                                               localidad_id, fecha_ini=fecha_ini, fecha_fin=fecha_fin))


def _detalles_f(programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id, localidad_id, curp, nombre,
                fecha_ini, fecha_fin, anio_ini, anio_fin, tipo) -> dict:
    return _f(programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id, localidad_id, curp=curp, nombre=nombre,
              fecha_ini=fecha_ini, fecha_fin=fecha_fin, anio_ini=anio_ini, anio_fin=anio_fin, tipo=tipo)


@router.get("/detalles")
def detalles(programa_ids: Programas = None, apoyo_id: Id = None, descripcion_apoyo_id: Id = None, estado_id: Id = None,
             municipio_id: Id = None, localidad_id: Id = None, curp: str | None = None, nombre: str | None = None,
             fecha_ini: date | None = None, fecha_fin: date | None = None, anio_ini: int | None = None,
             anio_fin: int | None = None, tipo: Literal["detallado", "concentrado"] = "detallado",
             actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return svc.detalles(cat.Ctx(db, actor), _detalles_f(programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id,
                                                        localidad_id, curp, nombre, fecha_ini, fecha_fin, anio_ini, anio_fin, tipo))


@router.get("/detalles/exportar")
def exportar_detalles(programa_ids: Programas = None, apoyo_id: Id = None, descripcion_apoyo_id: Id = None,
                      estado_id: Id = None, municipio_id: Id = None, localidad_id: Id = None, curp: str | None = None,
                      nombre: str | None = None, fecha_ini: date | None = None, fecha_fin: date | None = None,
                      anio_ini: int | None = None, anio_fin: int | None = None,
                      tipo: Literal["detallado", "concentrado"] = "detallado",
                      actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    datos, nombre_archivo = svc.exportar_detalles(cat.Ctx(db, actor), _detalles_f(
        programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id, localidad_id, curp, nombre,
        fecha_ini, fecha_fin, anio_ini, anio_fin, tipo))
    return Response(datos, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'})


@router.get("/comparativo")
def comparativo(programa_ids: Programas = None, apoyo_id: Id = None, descripcion_apoyo_id: Id = None,
                estado_id: Id = None, municipio_id: Id = None, localidad_id: Id = None,
                anio_ini: int | None = None, anio_fin: int | None = None,
                actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return svc.comparativo(cat.Ctx(db, actor), _f(programa_ids, apoyo_id, descripcion_apoyo_id, estado_id, municipio_id,
                                                  localidad_id, anio_ini=anio_ini, anio_fin=anio_fin))
