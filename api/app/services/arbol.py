"""Árbol de problemas y objetivos: causas↔medios y efectos↔fines (2 niveles, par espejo)."""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..deps import ActorCtx
from ..errors import ApiError
from ..models import ArbolCausaMedio, ArbolEfectoFin, ArbolEncabezado
from .bitacora import registrar
from .mir_base import programa_accesible, programa_info

# tipo -> (modelo, campo del lado "problema", campo del lado "objetivo")
TIPOS = {
    "causa": (ArbolCausaMedio, "texto_causa", "texto_medio"),
    "efecto": (ArbolEfectoFin, "texto_efecto", "texto_fin"),
}


def _dict(n, ca: str, ob: str) -> dict:
    return {"id": n.id, "numero": n.numero, "orden": n.orden, "padre_id": n.padre_id,
            ca: getattr(n, ca), ob: getattr(n, ob), "hijos": []}


def _anidar(nodos, ca: str, ob: str) -> list[dict]:
    por_id = {n.id: _dict(n, ca, ob) for n in nodos}
    raices = []
    for n in sorted(nodos, key=lambda x: x.orden):
        (por_id[n.padre_id]["hijos"] if n.padre_id in por_id else raices).append(por_id[n.id])
    return raices


def _nodos(db: Session, modelo, programa_id):
    return db.scalars(select(modelo).where(modelo.programa_id == programa_id)
                      .order_by(modelo.orden)).all()


def obtener(db: Session, actor: ActorCtx, programa_id: uuid.UUID) -> dict:
    p = programa_accesible(db, actor, programa_id)
    enc = db.get(ArbolEncabezado, p.id)
    out = {"programa": programa_info(db, p),
           "encabezado": {"problema": enc.problema if enc else None, "objetivo": enc.objetivo if enc else None}}
    for tipo, (modelo, ca, ob) in TIPOS.items():
        out[tipo + "s"] = _anidar(_nodos(db, modelo, p.id), ca, ob)
    return out


def editar_encabezado(db: Session, actor: ActorCtx, programa_id: uuid.UUID, d: dict) -> dict:
    p = programa_accesible(db, actor, programa_id)
    enc = db.get(ArbolEncabezado, p.id)
    if enc is None:
        enc = ArbolEncabezado(programa_id=p.id, municipio_id=actor.municipio_id)
        db.add(enc)
    for k in ("problema", "objetivo"):
        if k in d:
            setattr(enc, k, (d[k] or "").strip() or None)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="arbol.encabezado",
              entidad="programa", entidad_id=p.id, municipio_id=actor.municipio_id)
    return {"problema": enc.problema, "objetivo": enc.objetivo}


def _renumerar(db: Session, modelo, programa_id) -> None:
    """Deja `orden` consecutivo y `numero` ("1", "1.1") coherente tras altas y bajas."""
    nodos = _nodos(db, modelo, programa_id)
    hijos: dict = {}
    for n in nodos:
        hijos.setdefault(n.padre_id, []).append(n)
    for i, raiz in enumerate(sorted(hijos.get(None, []), key=lambda x: x.orden), 1):
        raiz.orden, raiz.numero = i, str(i)
        for j, h in enumerate(sorted(hijos.get(raiz.id, []), key=lambda x: x.orden), 1):
            h.orden, h.numero = j, f"{raiz.numero}.{j}"


def _cargar(db: Session, actor: ActorCtx, tipo: str, id: uuid.UUID):
    modelo = TIPOS[tipo][0]
    n = db.get(modelo, id)
    if n is None:
        raise ApiError(404, "NODO_NO_ENCONTRADO", "Nodo del árbol no encontrado")
    programa_accesible(db, actor, n.programa_id)
    return n


def _texto(d: dict, campo: str, obligatorio: bool) -> str:
    t = (d.get(campo) or "").strip()
    if obligatorio and not t:
        raise ApiError(422, "VALIDACION", "El texto es obligatorio", {campo: "Obligatorio"})
    return t


def crear(db: Session, actor: ActorCtx, programa_id: uuid.UUID, tipo: str, d: dict) -> dict:
    p = programa_accesible(db, actor, programa_id)
    modelo, ca, ob = TIPOS[tipo]
    padre = None
    if d.get("padre_id"):
        padre = db.get(modelo, d["padre_id"])
        if padre is None or padre.programa_id != p.id:
            raise ApiError(422, "PADRE_INVALIDO", "El nodo padre no existe en este programa",
                           {"padre_id": "Inválido"})
        if padre.padre_id is not None:
            raise ApiError(422, "NIVEL_MAXIMO", "El árbol tiene 2 niveles: no se puede anidar más",
                           {"padre_id": "Solo se permiten 2 niveles"})
    hermanos = [n for n in _nodos(db, modelo, p.id) if n.padre_id == (padre.id if padre else None)]
    orden = max((n.orden for n in hermanos), default=0) + 1
    n = modelo(programa_id=p.id, padre_id=padre.id if padre else None, orden=orden,
               numero=f"{padre.numero}.{orden}" if padre else str(orden),
               **{ca: _texto(d, ca, True), ob: _texto(d, ob, False)})
    db.add(n)
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion=f"arbol.{tipo}.crear",
              entidad=modelo.__tablename__, entidad_id=n.id, municipio_id=actor.municipio_id,
              detalle={"numero": n.numero})
    return _dict(n, ca, ob)


def editar(db: Session, actor: ActorCtx, tipo: str, id: uuid.UUID, d: dict) -> dict:
    """Edita el par espejo junto (causa+medio o efecto+fin): nunca por separado."""
    n = _cargar(db, actor, tipo, id)
    _, ca, ob = TIPOS[tipo]
    if ca in d:
        setattr(n, ca, _texto(d, ca, True))
    if ob in d:
        setattr(n, ob, _texto(d, ob, False))
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion=f"arbol.{tipo}.editar",
              entidad=type(n).__tablename__, entidad_id=n.id, municipio_id=actor.municipio_id,
              detalle={"numero": n.numero})
    return _dict(n, ca, ob)


def eliminar(db: Session, actor: ActorCtx, tipo: str, id: uuid.UUID) -> int:
    """Elimina el nodo y sus hijos; renumera a los hermanos. Devuelve cuántos nodos borró."""
    n = _cargar(db, actor, tipo, id)
    modelo = TIPOS[tipo][0]
    ids = [n.id, *db.scalars(select(modelo.id).where(modelo.padre_id == n.id)).all()]
    programa_id, numero = n.programa_id, n.numero
    db.execute(delete(modelo).where(modelo.padre_id == n.id))
    db.delete(n)
    db.flush()
    _renumerar(db, modelo, programa_id)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion=f"arbol.{tipo}.eliminar",
              entidad=modelo.__tablename__, entidad_id=id, municipio_id=actor.municipio_id,
              detalle={"numero": numero, "nodos_eliminados": len(ids)})
    return len(ids)
