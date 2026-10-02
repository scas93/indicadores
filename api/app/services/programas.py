import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import validators_planeacion as vp
from .. import validators_usuarios as vu
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import (CentroGestor, ClasificacionProgramatica, Eje, Estrategia, Programa, Subtema,
                      UsuarioPrograma)
from .bitacora import registrar


def a_dict(p: Programa) -> dict:
    return {"id": p.id, "ejercicio_fiscal": p.ejercicio_fiscal, "clave": p.clave, "nombre": p.nombre,
            "centro_gestor_id": p.centro_gestor_id, "subtema_id": p.subtema_id,
            "estrategia_id": p.estrategia_id,
            "clasificacion_programatica_id": p.clasificacion_programatica_id, "activo": p.activo}


def visibles(db: Session, tipo: str | None, usuario_id: uuid.UUID | None):
    """Programas que el usuario puede ver/usar: None = todos (administrador, alcalde, super admin),
    si no, solo los de su matriz (`usuario_programa`). Punto único para selectores y reportes
    presentes y futuros: se lee de la base en cada petición, nunca de la sesión."""
    if tipo is None:
        return None
    asignados = db.scalars(select(UsuarioPrograma.programa_id).where(
        UsuarioPrograma.usuario_id == usuario_id)).all()
    return vu.programas_visibles(tipo, asignados)


def listar(db: Session, actor: ActorCtx, ejercicio: int | None, centro_gestor_id, activo: bool | None,
           q: str | None) -> list[dict]:
    stmt = select(Programa)
    ver = visibles(db, actor.tipo_usuario, actor.usuario_id)
    if ver is not None:
        stmt = stmt.where(Programa.id.in_(ver))
    if ejercicio:
        stmt = stmt.where(Programa.ejercicio_fiscal == ejercicio)
    if centro_gestor_id:
        stmt = stmt.where(Programa.centro_gestor_id == centro_gestor_id)
    if activo is not None:
        stmt = stmt.where(Programa.activo == activo)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(Programa.nombre).like(like) | func.lower(Programa.clave).like(like))
    return [a_dict(p) for p in db.scalars(stmt.order_by(Programa.ejercicio_fiscal.desc(), Programa.clave))]


def _cargar(db: Session, actor: ActorCtx, id: uuid.UUID) -> Programa:
    p = db.get(Programa, id)
    ver = visibles(db, actor.tipo_usuario, actor.usuario_id)
    if p is None or (ver is not None and p.id not in ver):
        raise ApiError(404, "PROGRAMA_NO_ENCONTRADO", "Programa no encontrado")
    return p


def _validar_refs(db: Session, centro_id, subtema_id, estrategia_id, clasif_id) -> None:
    c = db.get(CentroGestor, centro_id) if centro_id else None
    s = db.get(Subtema, subtema_id) if subtema_id else None
    e = db.get(Estrategia, estrategia_id) if estrategia_id else None
    s_ref = None
    if s is not None:
        eje = db.get(Eje, s.eje_id)
        s_ref = vp.Ref(s.id, s.activo, s.eje_id, eje.centro_gestor_id if eje else None)
    vp.validar_referencias_programa(
        vp.Ref(c.id, c.activo) if c else None, s_ref,
        vp.Ref(e.id, e.activo, e.subtema_id) if e else None,
        subtema_pedido=subtema_id is not None, estrategia_pedida=estrategia_id is not None)
    if clasif_id and db.get(ClasificacionProgramatica, clasif_id) is None:
        raise ApiError(422, "CLASIFICACION_INVALIDA", "Clasificación programática inválida",
                       {"clasificacion_programatica_id": "Inválida"})


def _guardar(db: Session, p: Programa) -> None:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CLAVE_DUPLICADA", "La clave ya existe en ese ejercicio",
                       {"clave": "Ya existe en ese ejercicio"})


def _clave_libre(db: Session, ejercicio: int, clave: str, excepto: uuid.UUID | None = None) -> None:
    stmt = select(Programa.id).where(Programa.ejercicio_fiscal == ejercicio, Programa.clave == clave)
    if excepto:
        stmt = stmt.where(Programa.id != excepto)
    if db.scalar(stmt) is not None:
        raise ApiError(409, "CLAVE_DUPLICADA", "La clave ya existe en ese ejercicio",
                       {"clave": "Ya existe en ese ejercicio"})


def crear(db: Session, actor: ActorCtx, d: dict) -> Programa:
    clave, nombre = vp.validar_clave_nombre(d.get("clave"), d.get("nombre"))
    ejercicio = vp.validar_ejercicio(d.get("ejercicio_fiscal"))
    _validar_refs(db, d.get("centro_gestor_id"), d.get("subtema_id"), d.get("estrategia_id"),
                  d.get("clasificacion_programatica_id"))
    _clave_libre(db, ejercicio, clave)
    p = Programa(municipio_id=actor.municipio_id, ejercicio_fiscal=ejercicio, clave=clave, nombre=nombre,
                 centro_gestor_id=d["centro_gestor_id"], subtema_id=d.get("subtema_id"),
                 estrategia_id=d.get("estrategia_id"),
                 clasificacion_programatica_id=d.get("clasificacion_programatica_id"), activo=True)
    db.add(p)
    _guardar(db, p)
    if actor.usuario_id and visibles(db, actor.tipo_usuario, actor.usuario_id) is not None:
        # quien crea un programa y solo ve los asignados lo recibe asignado (si no, no lo vería)
        db.add(UsuarioPrograma(usuario_id=actor.usuario_id, programa_id=p.id, municipio_id=actor.municipio_id))
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="programa.crear",
              entidad="programa", entidad_id=p.id, municipio_id=actor.municipio_id,
              detalle={"clave": clave, "ejercicio_fiscal": ejercicio})
    return p


def editar(db: Session, actor: ActorCtx, id: uuid.UUID, cambios: dict) -> Programa:
    p = _cargar(db, actor, id)
    clave, nombre = vp.validar_clave_nombre(cambios.get("clave", p.clave), cambios.get("nombre", p.nombre))
    ejercicio = vp.validar_ejercicio(cambios.get("ejercicio_fiscal", p.ejercicio_fiscal))
    nuevo = {k: cambios.get(k, getattr(p, k)) for k in (
        "centro_gestor_id", "subtema_id", "estrategia_id", "clasificacion_programatica_id")}
    # Solo se re-validan las referencias si se movieron: un programa existente puede seguir
    # colgando de padres que hoy están deshabilitados.
    if any(k in cambios and cambios[k] != getattr(p, k) for k in nuevo):
        _validar_refs(db, nuevo["centro_gestor_id"], nuevo["subtema_id"], nuevo["estrategia_id"],
                      nuevo["clasificacion_programatica_id"])
    _clave_libre(db, ejercicio, clave, p.id)
    antes = p.activo
    p.clave, p.nombre, p.ejercicio_fiscal = clave, nombre, ejercicio
    for k, val in nuevo.items():
        setattr(p, k, val)
    if cambios.get("activo") is not None:
        p.activo = bool(cambios["activo"])
    _guardar(db, p)
    accion = "programa.editar" if antes == p.activo else f"programa.{'habilitar' if p.activo else 'deshabilitar'}"
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion=accion,
              entidad="programa", entidad_id=p.id, municipio_id=actor.municipio_id, detalle={"clave": p.clave})
    return p


def duplicar(db: Session, actor: ActorCtx, id: uuid.UUID, ejercicio_destino: int, clave_nueva: str,
             nombre: str | None) -> Programa:
    """Copia a otro ejercicio con clave nueva REUTILIZANDO centro gestor, subtema y estrategia
    (no tienen versión por ejercicio); el original no se modifica."""
    o = _cargar(db, actor, id)
    en_destino = set(db.scalars(select(Programa.clave).where(
        Programa.ejercicio_fiscal == ejercicio_destino)).all())
    vp.validar_duplicado_programa(o.ejercicio_fiscal, o.clave, ejercicio_destino, clave_nueva, en_destino)
    n = Programa(municipio_id=actor.municipio_id, ejercicio_fiscal=ejercicio_destino,
                 clave=clave_nueva.strip(), nombre=(nombre or "").strip() or o.nombre,
                 centro_gestor_id=o.centro_gestor_id, subtema_id=o.subtema_id,
                 estrategia_id=o.estrategia_id,
                 clasificacion_programatica_id=o.clasificacion_programatica_id, activo=True)
    db.add(n)
    _guardar(db, n)
    if actor.usuario_id and visibles(db, actor.tipo_usuario, actor.usuario_id) is not None:
        db.add(UsuarioPrograma(usuario_id=actor.usuario_id, programa_id=n.id, municipio_id=actor.municipio_id))
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="programa.duplicar",
              entidad="programa", entidad_id=n.id, municipio_id=actor.municipio_id,
              detalle={"origen": str(o.id), "ejercicio_destino": ejercicio_destino, "clave": n.clave})
    return n
