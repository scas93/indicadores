"""Matriz usuarios × programas."""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import validators_usuarios as vu
from ..deps import ActorCtx
from ..models import CentroGestor, Programa, Usuario, UsuarioPrograma
from . import usuarios as svc
from .bitacora import registrar


def obtener(db: Session, ejercicio: int, centro_gestor_id: uuid.UUID | None, tipo: str | None,
            q: str | None) -> dict:
    ps = (select(Programa, CentroGestor).join(CentroGestor, CentroGestor.id == Programa.centro_gestor_id)
          .where(Programa.ejercicio_fiscal == ejercicio, Programa.activo.is_(True)))
    if centro_gestor_id:
        ps = ps.where(Programa.centro_gestor_id == centro_gestor_id)
    filas = db.execute(ps.order_by(CentroGestor.clave, Programa.clave)).all()
    us = select(Usuario).where(Usuario.activo.is_(True))
    if tipo:
        us = us.where(Usuario.tipo == tipo)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        us = us.where(or_(func.lower(Usuario.nombre).like(like), func.lower(Usuario.usuario).like(like)))
    usuarios = db.scalars(us.order_by(Usuario.nombre)).all()
    pids, uids = [p.id for p, _ in filas], [u.id for u in usuarios]
    asign = db.execute(select(UsuarioPrograma.usuario_id, UsuarioPrograma.programa_id).where(
        UsuarioPrograma.programa_id.in_(pids), UsuarioPrograma.usuario_id.in_(uids))).all() \
        if pids and uids else []
    centros = {}
    for _, c in filas:
        centros.setdefault(c.id, {"id": c.id, "clave": c.clave, "nombre": c.nombre})
    return {"ejercicio": ejercicio, "centros_gestores": list(centros.values()),
            "programas": [{"id": p.id, "clave": p.clave, "nombre": p.nombre,
                           "centro_gestor_id": p.centro_gestor_id} for p, _ in filas],
            "usuarios": [{"id": u.id, "usuario": u.usuario, "nombre": u.nombre, "tipo": u.tipo.value}
                         for u in usuarios],
            "asignaciones": [[a, b] for a, b in asign]}


def guardar(db: Session, actor: ActorCtx, altas: list[tuple], bajas: list[tuple]) -> dict:
    """Todo en una transacción: o se aplican las altas y bajas, o ninguna (el commit lo hace el
    handler). El resumen devuelto es exactamente lo que se guardó."""
    a, b = svc.aplicar_cambios_asignacion(db, actor, altas, bajas)
    resumen = vu.resumen_matriz(a, b)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="matriz.guardar",
              entidad="usuario_programa", municipio_id=actor.municipio_id,
              detalle={"resumen": resumen, "altas": a, "bajas": b})
    return {"altas": a, "bajas": b, "resumen": resumen}
