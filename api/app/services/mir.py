"""Matriz de indicadores: filas (fin, propósito, componentes, actividades) e indicadores."""
import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import calculo
from .. import validators_mir as vm
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import (Algoritmo, AvanceMensual, DimensionIndicador, ElementoMatriz, Frecuencia,
                      Indicador, MetaAnual, NivelMatriz, Programa, TipoIndicador)
from .bitacora import registrar
from .mir_base import elemento_accesible, indicador_accesible, programa_accesible, programa_info

CAMPOS_ELEMENTO = ("resumen_narrativo", "medios_verificacion", "supuestos", "evidencia")
CAMPOS_FICHA = ("tipo", "prioritario", "nombre", "interpretacion", "dimension", "frecuencia_id",
                "unidad_medida", "algoritmo", "unidad_a", "unidad_b")
COLORES = ("verde", "amarillo", "rojo")
_ENUMS = {"tipo": TipoIndicador, "dimension": DimensionIndicador, "algoritmo": Algoritmo}


def _f(d: Decimal | None) -> float | None:
    return None if d is None else float(d)


# --------------------------------------------------------------------------- serialización
def metas_de(db: Session, indicador_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[MetaAnual]]:
    out: dict = {i: [] for i in indicador_ids}
    if indicador_ids:
        for m in db.scalars(select(MetaAnual).where(MetaAnual.indicador_id.in_(indicador_ids))
                            .order_by(MetaAnual.anio)):
            out[m.indicador_id].append(m)
    return out


def indicador_dict(i: Indicador, metas: list[MetaAnual]) -> dict:
    solo_a = i.algoritmo == Algoritmo.a
    return {
        "id": i.id, "elemento_matriz_id": i.elemento_matriz_id,
        "ficha": {
            "tipo": i.tipo.value, "prioritario": i.prioritario, "nombre": i.nombre,
            "interpretacion": i.interpretacion, "dimension": i.dimension.value if i.dimension else None,
            "frecuencia_id": i.frecuencia_id, "unidad_medida": i.unidad_medida,
            "algoritmo": i.algoritmo.value if i.algoritmo else None, "unidad_a": i.unidad_a,
            "unidad_b": None if solo_a else i.unidad_b,
        },
        "metas": {
            "anio_base": i.anio_base, "meta_administracion": _f(i.meta_administracion),
            "anuales": [{"anio": m.anio, "valor_a_programado": _f(m.valor_a_programado),
                         # con "solo A" la variable B no aparece en ningún lado (aunque haya B guardado)
                         "valor_b_programado": None if solo_a else _f(m.valor_b_programado),
                         "es_ejercicio_fiscal": m.es_ejercicio_fiscal} for m in metas],
        },
        "rangos": {c: {"desde": _f(getattr(i, f"rango_{c}_desde")), "hasta": _f(getattr(i, f"rango_{c}_hasta"))}
                   for c in COLORES},
    }


def elemento_dict(e: ElementoMatriz) -> dict:
    return {"id": e.id, "nivel": e.nivel.value, "numero": e.numero, "orden": e.orden, "padre_id": e.padre_id,
            **{c: getattr(e, c) for c in CAMPOS_ELEMENTO}, "indicadores": []}


# --------------------------------------------------------------------------- matriz
def asegurar_base(db: Session, programa: Programa) -> None:
    """Fin y Propósito (únicos) se crean vacíos la primera vez que se entra al programa."""
    existentes = set(db.scalars(select(ElementoMatriz.nivel).where(
        ElementoMatriz.programa_id == programa.id,
        ElementoMatriz.nivel.in_([NivelMatriz.fin, NivelMatriz.proposito]))).all())
    for nivel in (NivelMatriz.fin, NivelMatriz.proposito):
        if nivel in existentes:
            continue
        try:
            with db.begin_nested():
                db.add(ElementoMatriz(programa_id=programa.id, nivel=nivel))
                db.flush()
        except IntegrityError:
            pass  # otra petición lo creó primero: el índice único parcial garantiza uno solo


def alta_nivel_unico(db: Session, programa: Programa, nivel: str) -> ElementoMatriz:
    """Alta explícita de Fin/Propósito: rechaza el segundo."""
    existentes = db.scalars(select(ElementoMatriz.nivel).where(
        ElementoMatriz.programa_id == programa.id)).all()
    vm.validar_alta_nivel_unico(nivel, [n.value for n in existentes])
    e = ElementoMatriz(programa_id=programa.id, nivel=NivelMatriz(nivel))
    db.add(e)
    db.flush()
    return e


def obtener(db: Session, actor: ActorCtx, programa_id: uuid.UUID) -> dict:
    p = programa_accesible(db, actor, programa_id)
    asegurar_base(db, p)
    elementos = db.scalars(select(ElementoMatriz).where(ElementoMatriz.programa_id == p.id)
                           .order_by(ElementoMatriz.orden)).all()
    indicadores = db.scalars(select(Indicador).where(
        Indicador.elemento_matriz_id.in_([e.id for e in elementos]))
        .order_by(Indicador.created_at)).all() if elementos else []
    metas = metas_de(db, [i.id for i in indicadores])
    por_el: dict = {}
    for i in indicadores:
        por_el.setdefault(i.elemento_matriz_id, []).append(indicador_dict(i, metas[i.id]))
    dicts = {e.id: elemento_dict(e) for e in elementos}
    for eid, lista in por_el.items():
        dicts[eid]["indicadores"] = lista
    out = {"programa": programa_info(db, p), "fin": None, "proposito": None, "componentes": []}
    comps = {}
    for e in elementos:
        d = dicts[e.id]
        if e.nivel == NivelMatriz.fin:
            out["fin"] = d
        elif e.nivel == NivelMatriz.proposito:
            out["proposito"] = d
        elif e.nivel == NivelMatriz.componente:
            d["actividades"] = []
            comps[e.id] = d
            out["componentes"].append(d)
    for e in elementos:
        if e.nivel == NivelMatriz.actividad and e.padre_id in comps:
            comps[e.padre_id]["actividades"].append(dicts[e.id])
    return out


def _aplicar_elemento(e: ElementoMatriz, d: dict) -> None:
    for c in CAMPOS_ELEMENTO:
        if c in d:
            v = d[c]
            setattr(e, c, (v or "").strip() if c != "evidencia" else ((v or "").strip() or None))


def _renumerar_matriz(db: Session, programa_id: uuid.UUID) -> None:
    comps = db.scalars(select(ElementoMatriz).where(
        ElementoMatriz.programa_id == programa_id, ElementoMatriz.nivel == NivelMatriz.componente)
        .order_by(ElementoMatriz.orden)).all()
    for i, c in enumerate(comps, 1):
        c.orden, c.numero = i, str(i)
        acts = db.scalars(select(ElementoMatriz).where(
            ElementoMatriz.padre_id == c.id).order_by(ElementoMatriz.orden)).all()
        for j, a in enumerate(acts, 1):
            a.orden, a.numero = j, f"{c.numero}.{j}"


def crear_componente(db: Session, actor: ActorCtx, programa_id: uuid.UUID, d: dict) -> dict:
    p = programa_accesible(db, actor, programa_id)
    asegurar_base(db, p)
    orden = max(db.scalars(select(ElementoMatriz.orden).where(
        ElementoMatriz.programa_id == p.id, ElementoMatriz.nivel == NivelMatriz.componente)).all(),
        default=0) + 1
    e = ElementoMatriz(programa_id=p.id, nivel=NivelMatriz.componente, orden=orden, numero=str(orden))
    _aplicar_elemento(e, d)
    db.add(e)
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="matriz.componente.crear",
              entidad="elemento_matriz", entidad_id=e.id, municipio_id=actor.municipio_id,
              detalle={"numero": e.numero})
    return elemento_dict(e)


def crear_actividad(db: Session, actor: ActorCtx, componente_id: uuid.UUID, d: dict) -> dict:
    comp, p = elemento_accesible(db, actor, componente_id)
    if comp.nivel != NivelMatriz.componente:
        raise ApiError(422, "PADRE_INVALIDO", "Las actividades cuelgan de un componente",
                       {"componente_id": "No es un componente"})
    orden = max(db.scalars(select(ElementoMatriz.orden).where(ElementoMatriz.padre_id == comp.id)).all(),
                default=0) + 1
    e = ElementoMatriz(programa_id=p.id, nivel=NivelMatriz.actividad, padre_id=comp.id, orden=orden,
                       numero=f"{comp.numero}.{orden}")
    _aplicar_elemento(e, d)
    db.add(e)
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="matriz.actividad.crear",
              entidad="elemento_matriz", entidad_id=e.id, municipio_id=actor.municipio_id,
              detalle={"numero": e.numero})
    return elemento_dict(e)


def editar_elemento(db: Session, actor: ActorCtx, id: uuid.UUID, d: dict) -> dict:
    e, _ = elemento_accesible(db, actor, id)
    _aplicar_elemento(e, d)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="matriz.elemento.editar",
              entidad="elemento_matriz", entidad_id=e.id, municipio_id=actor.municipio_id,
              detalle={"nivel": e.nivel.value, "numero": e.numero})
    return elemento_dict(e)


def eliminar_elemento(db: Session, actor: ActorCtx, id: uuid.UUID) -> dict:
    """Solo componentes y actividades. Un componente arrastra en cascada sus actividades y los
    indicadores (con metas y avances) de todos ellos; queda en bitácora."""
    e, p = elemento_accesible(db, actor, id)
    vm.validar_eliminable(e.nivel.value)
    ids = [e.id]
    if e.nivel == NivelMatriz.componente:
        ids += list(db.scalars(select(ElementoMatriz.id).where(ElementoMatriz.padre_id == e.id)).all())
    ind_ids = list(db.scalars(select(Indicador.id).where(Indicador.elemento_matriz_id.in_(ids))).all())
    if ind_ids:
        db.execute(delete(AvanceMensual).where(AvanceMensual.indicador_id.in_(ind_ids)))
        db.execute(delete(MetaAnual).where(MetaAnual.indicador_id.in_(ind_ids)))
        db.execute(delete(Indicador).where(Indicador.id.in_(ind_ids)))
    db.execute(delete(ElementoMatriz).where(ElementoMatriz.padre_id == e.id))
    detalle = {"nivel": e.nivel.value, "numero": e.numero, "elementos_eliminados": len(ids),
               "indicadores_eliminados": len(ind_ids)}
    db.delete(e)
    db.flush()
    _renumerar_matriz(db, p.id)
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id,
              accion=f"matriz.{detalle['nivel']}.eliminar", entidad="elemento_matriz", entidad_id=id,
              municipio_id=actor.municipio_id, detalle=detalle)
    return detalle


# --------------------------------------------------------------------------- indicadores
def _frecuencia_valida(db: Session, frecuencia_id) -> None:
    f = db.get(Frecuencia, frecuencia_id)
    if f is None or not f.activo:
        raise ApiError(422, "FRECUENCIA_INVALIDA", "Frecuencia inválida o deshabilitada",
                       {"frecuencia_id": "Inválida"})


def _rangos_actuales(i: Indicador) -> dict[str, calculo.Rango]:
    return {c: (getattr(i, f"rango_{c}_desde"), getattr(i, f"rango_{c}_hasta")) for c in COLORES}


def _aplicar(db: Session, actor: ActorCtx, i: Indicador, d: dict, *, alta: bool) -> None:
    ficha = d.get("ficha") or {}
    if alta:
        if not ficha.get("tipo"):
            raise ApiError(422, "VALIDACION", "El tipo es obligatorio", {"tipo": "Obligatorio"})
        if not (ficha.get("nombre") or "").strip():
            raise ApiError(422, "VALIDACION", "El nombre del indicador es obligatorio", {"nombre": "Obligatorio"})
    elif "nombre" in ficha and not (ficha["nombre"] or "").strip():
        raise ApiError(422, "VALIDACION", "El nombre del indicador es obligatorio", {"nombre": "Obligatorio"})
    if ficha.get("tipo") is None and "tipo" in ficha:
        raise ApiError(422, "VALIDACION", "El tipo es obligatorio", {"tipo": "Obligatorio"})
    if ficha.get("frecuencia_id") and ficha["frecuencia_id"] != i.frecuencia_id:
        _frecuencia_valida(db, ficha["frecuencia_id"])
    for c in CAMPOS_FICHA:
        if c in ficha:
            v = ficha[c]
            if isinstance(v, str):
                v = v.strip()
            if c in _ENUMS and v is not None:
                v = _ENUMS[c](v)
            if c == "unidad_b" and v == "":
                v = None
            setattr(i, c, v)
    if i.algoritmo == Algoritmo.a:
        i.unidad_b = None  # B bloqueada: no se pide ni se guarda (los B ya capturados no se tocan)
    algoritmo = i.algoritmo.value if i.algoritmo else None

    rangos = d.get("rangos")
    if rangos is not None:
        actuales = _rangos_actuales(i)
        for c in COLORES:
            if c in rangos and rangos[c] is not None:
                actuales[c] = (vm.normalizar_valor(rangos[c].get("desde"), f"rango_{c}"),
                               vm.normalizar_valor(rangos[c].get("hasta"), f"rango_{c}"))
        vm.validar_rangos(*(actuales[c] for c in COLORES))
        for c in COLORES:
            setattr(i, f"rango_{c}_desde", actuales[c][0])
            setattr(i, f"rango_{c}_hasta", actuales[c][1])

    metas = d.get("metas") or {}
    if "anio_base" in metas:
        i.anio_base = vm.validar_anio(metas["anio_base"]) if metas["anio_base"] is not None else None
    if "meta_administracion" in metas:
        i.meta_administracion = vm.normalizar_valor(metas["meta_administracion"], "meta_administracion")
    anuales = metas.get("anuales")
    if anuales:
        # no se guarda una meta anual si el indicador no tiene algoritmo y frecuencia (422)
        vm.validar_metas_permitidas(algoritmo, i.frecuencia_id)
    if anuales is not None:
        vm.validar_metas_anuales(algoritmo, anuales)
        if i not in db:
            db.add(i)  # las metas referencian al indicador: primero la fila del indicador
        db.flush()
        existentes = {m.anio: m for m in db.scalars(select(MetaAnual).where(MetaAnual.indicador_id == i.id))}
        nuevos = {m["anio"] for m in anuales}
        for anio, m in existentes.items():
            if anio not in nuevos:
                db.delete(m)
        for m in anuales:
            fila = existentes.get(m["anio"])
            if fila is None:
                fila = MetaAnual(indicador_id=i.id, anio=m["anio"])
                db.add(fila)
            fila.valor_a_programado = vm.normalizar_valor(m.get("valor_a_programado"), "valor_a_programado")
            if algoritmo != "a":  # con "solo A" la B guardada de antes se conserva intacta
                fila.valor_b_programado = vm.normalizar_valor(m.get("valor_b_programado"), "valor_b_programado")
            fila.es_ejercicio_fiscal = bool(m.get("es_ejercicio_fiscal"))
    elif i in db and ("algoritmo" in ficha or "frecuencia_id" in ficha):
        # quitar algoritmo/frecuencia a un indicador que ya tiene metas dejaría metas huérfanas
        if db.scalar(select(MetaAnual.id).where(MetaAnual.indicador_id == i.id).limit(1)):
            vm.validar_metas_permitidas(algoritmo, i.frecuencia_id)


def crear_indicador(db: Session, actor: ActorCtx, elemento_id: uuid.UUID, d: dict) -> dict:
    """Alta completa en una operación: M.I.R., ficha técnica, metas por año y rangos."""
    e, _ = elemento_accesible(db, actor, elemento_id)
    i = Indicador(id=uuid.uuid4(), elemento_matriz_id=e.id, prioritario=False)
    _aplicar(db, actor, i, d, alta=True)
    if d.get("mir"):
        _aplicar_elemento(e, d["mir"])
    if i not in db:
        db.add(i)
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="indicador.crear",
              entidad="indicador", entidad_id=i.id, municipio_id=actor.municipio_id,
              detalle={"nombre": i.nombre, "elemento": e.nivel.value})
    return indicador_dict(i, metas_de(db, [i.id])[i.id])


def editar_indicador(db: Session, actor: ActorCtx, id: uuid.UUID, d: dict) -> dict:
    i, e, _ = indicador_accesible(db, actor, id)
    _aplicar(db, actor, i, d, alta=False)
    if d.get("mir"):
        _aplicar_elemento(e, d["mir"])
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="indicador.editar",
              entidad="indicador", entidad_id=i.id, municipio_id=actor.municipio_id,
              detalle={"partes": sorted(d)})
    return indicador_dict(i, metas_de(db, [i.id])[i.id])
