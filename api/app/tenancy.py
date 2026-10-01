"""Aislamiento por municipio_id en UNA capa común.

Una Session con `info["municipio_id"]` fijado:
  * agrega `WHERE municipio_id = :id` a todo SELECT/UPDATE/DELETE sobre cualquier modelo
    que herede TenantMixin (with_loader_criteria), incluidos joins y session.get().
  * rellena `municipio_id` en los INSERT y rechaza escribir o mover filas de otro municipio.
Los endpoints de ámbito municipio reciben una Session así (ver deps.py); un desarrollador
no puede olvidar el filtro porque no lo escribe.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from .errors import TenantViolation
from .models import TenantMixin

TENANT_KEY = "municipio_id"


def scope_session(db: Session, municipio_id) -> Session:
    db.info[TENANT_KEY] = municipio_id
    return db


@event.listens_for(Session, "do_orm_execute")
def _filtrar_por_municipio(state) -> None:
    mid = state.session.info.get(TENANT_KEY)
    if mid is None or state.is_column_load or state.is_relationship_load:
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantMixin, lambda cls: cls.municipio_id == mid, include_aliases=True)
    )


@event.listens_for(Session, "before_flush")
def _validar_escrituras(session: Session, flush_context, instances) -> None:
    mid = session.info.get(TENANT_KEY)
    if mid is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantMixin):
            if obj.municipio_id is None:
                obj.municipio_id = mid
            elif obj.municipio_id != mid:
                raise TenantViolation(f"{type(obj).__name__} de otro municipio")
    for obj in session.dirty:
        if isinstance(obj, TenantMixin) and obj.municipio_id != mid:
            raise TenantViolation(f"{type(obj).__name__} de otro municipio")
