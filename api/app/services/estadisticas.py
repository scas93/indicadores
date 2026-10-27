"""Fase 3 — Estadísticas: capa de lectura y agregación sobre Fase 2. No guarda nada.

Alcance: la misma regla de las demás fases (`programas.visibles`): administrador y alcalde ven todos
los programas del municipio; el resto, solo los de su `usuario_programa`. Es la única fuente de
alcance de conteos, detalle, selectores y exportaciones. Cumplimiento y color se calculan con `services.cumplimiento` / `app.calculo` (Fase 2); `app.calculo_estadisticas` solo
decide qué valor se compara según el modo.
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calculo
from .. import calculo_estadisticas as ce
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import (CentroGestor, Eje, ElementoMatriz, Indicador, MetaAnual, NivelMatriz, Programa,
                      Subtema)
from . import cumplimiento as cump
from .programas import visibles

_NIVEL_ORDEN = {NivelMatriz.fin: 0, NivelMatriz.proposito: 1, NivelMatriz.componente: 2,
                NivelMatriz.actividad: 3}


@dataclass
class Fila:
    """Un indicador del universo, ya evaluado en el año pedido."""
    ind: Indicador
    elem: ElementoMatriz
    prog: Programa
    cg: CentroGestor
    eje: Eje | None
    meta: MetaAnual
    avances: dict[int, tuple[Decimal | None, Decimal | None]]
    res: calculo.Resultado
    meta_num: Decimal | None

    def evaluar(self, modo: str) -> tuple[Decimal | None, str]:
        return ce.valor_y_color(modo, self.res, self.meta_num, *calculo.rangos_de(self.ind))


def validar_modo(modo: str) -> str:
    if modo not in ce.MODOS:
        raise ApiError(422, "VALIDACION", "Tipo de cumplimiento inválido",
                       {"tipo_cumplimiento": f"Debe ser uno de: {', '.join(ce.MODOS)}"})
    return modo


def programas_en_alcance(db: Session, actor: ActorCtx) -> set[uuid.UUID]:
    ver = visibles(db, actor.tipo_usuario, actor.usuario_id)
    if ver is None:  # administrador, alcalde: todos los programas del municipio (Session ya aislada)
        return set(db.scalars(select(Programa.id)))
    return set(ver)


def universo(db: Session, actor: ActorCtx, anio: int, *, centro_gestor_ids: list[uuid.UUID] | None = None,
             eje_ids: list[uuid.UUID] | None = None, programa_id: uuid.UUID | None = None) -> list[Fila]:
    """Indicadores del año dentro del alcance del usuario (y de los filtros), con meta y avances.
    Entran solo los que tienen meta anual programada y al menos un mes capturado en `anio`."""
    alcance = programas_en_alcance(db, actor)
    if not alcance:
        return []
    stmt = (select(Indicador, ElementoMatriz, Programa, CentroGestor, Eje)
            .join(ElementoMatriz, ElementoMatriz.id == Indicador.elemento_matriz_id)
            .join(Programa, Programa.id == ElementoMatriz.programa_id)
            .join(CentroGestor, CentroGestor.id == Programa.centro_gestor_id)
            .outerjoin(Subtema, Subtema.id == Programa.subtema_id)
            .outerjoin(Eje, Eje.id == Subtema.eje_id)
            .where(Programa.id.in_(alcance)))
    if centro_gestor_ids:
        stmt = stmt.where(Programa.centro_gestor_id.in_(centro_gestor_ids))
    if eje_ids:
        stmt = stmt.where(Eje.id.in_(eje_ids))
    if programa_id:
        stmt = stmt.where(Programa.id == programa_id)
    filas = db.execute(stmt).all()
    if not filas:
        return []
    ids = [f[0].id for f in filas]
    metas = {m.indicador_id: m for m in db.scalars(
        select(MetaAnual).where(MetaAnual.indicador_id.in_(ids), MetaAnual.anio == anio))}
    avances = cump.avances_del_anio(db, ids, anio)
    out: list[Fila] = []
    for ind, elem, prog, cg, eje in filas:
        meta = metas.get(ind.id)
        meses = avances.get(ind.id, {})
        if meta is None or not ce.indicador_con_datos(meta.valor_a_programado, meses.values()):
            continue
        algoritmo = ind.algoritmo.value if ind.algoritmo else None
        out.append(Fila(ind, elem, prog, cg, eje, meta, meses, cump.evaluar_indicador(ind, meses),
                        ce.meta_numerica(algoritmo, meta.valor_a_programado, meta.valor_b_programado)))
    # Orden de la MIR: Fin, Propósito, Componentes y, después, las Actividades agrupadas por su componente
    padres = {e.padre_id for _, e, *_ in filas if e.padre_id}
    orden_padre = {e.id: e.orden for e in db.scalars(select(ElementoMatriz).where(ElementoMatriz.id.in_(padres)))} if padres else {}
    out.sort(key=lambda f: (f.cg.clave, f.prog.clave, _NIVEL_ORDEN[f.elem.nivel], orden_padre.get(f.elem.padre_id, 0),
                            f.elem.orden, f.ind.created_at))
    return out


# --------------------------------------------------------------------------- conteos
def _grupo(id_, nombre: str, filas: list[Fila], modo: str) -> dict:
    return {"id": id_, "nombre": nombre, **ce.contar(f.evaluar(modo)[1] for f in filas)}


def por_dependencia(db: Session, actor: ActorCtx, anio: int, modo: str,
                    centro_gestor_ids: list[uuid.UUID] | None) -> dict:
    """Un grupo por centro gestor. Sin filtro: los centros donde el usuario tiene programas. Con
    filtro: cada uno de los pedidos, en 0 si el usuario no tiene programas ahí (no es error)."""
    validar_modo(modo)
    filas = universo(db, actor, anio, centro_gestor_ids=centro_gestor_ids)
    if centro_gestor_ids:
        cgs = list(db.scalars(select(CentroGestor).where(CentroGestor.id.in_(centro_gestor_ids))
                              .order_by(CentroGestor.clave)))
    else:
        alcance = programas_en_alcance(db, actor)
        cgs = list(db.scalars(select(CentroGestor).where(CentroGestor.id.in_(
            select(Programa.centro_gestor_id).where(Programa.id.in_(alcance)))).order_by(CentroGestor.clave))) \
            if alcance else []
    return {"anio": anio, "tipo_cumplimiento": modo,
            "grupos": [_grupo(c.id, c.nombre, [f for f in filas if f.cg.id == c.id], modo) for c in cgs]}


def por_eje(db: Session, actor: ActorCtx, anio: int, modo: str, eje_ids: list[uuid.UUID] | None) -> dict:
    """Un grupo por eje. Los programas sin subtema (y por tanto sin eje) caen en "Sin eje" para que
    el total coincida con el de los demás reportes (solo cuando no se filtra por ejes)."""
    validar_modo(modo)
    filas = universo(db, actor, anio, eje_ids=eje_ids)
    if eje_ids:
        ejes = list(db.scalars(select(Eje).where(Eje.id.in_(eje_ids)).order_by(Eje.clave)))
    else:
        alcance = programas_en_alcance(db, actor)
        ejes = list(db.scalars(select(Eje).where(Eje.id.in_(
            select(Subtema.eje_id).join(Programa, Programa.subtema_id == Subtema.id)
            .where(Programa.id.in_(alcance)))).order_by(Eje.clave))) if alcance else []
    grupos = [_grupo(e.id, e.nombre, [f for f in filas if f.eje and f.eje.id == e.id], modo) for e in ejes]
    sin_eje = [f for f in filas if f.eje is None]
    if sin_eje and not eje_ids:
        grupos.append(_grupo(None, "Sin eje", sin_eje, modo))
    return {"anio": anio, "tipo_cumplimiento": modo, "grupos": grupos}


def cumplimiento_metas(db: Session, actor: ActorCtx, anio: int, modo: str, centro_gestor_id: uuid.UUID) -> dict:
    """Conteo de UNA dependencia (el front calcula el % sobre el total para cada color)."""
    return por_dependencia(db, actor, anio, modo, [centro_gestor_id])


def consolidado(db: Session, actor: ActorCtx, anio: int, modo: str,
                centro_gestor_ids: list[uuid.UUID] | None) -> dict:
    """Mismos conteos que Dependencias; el front los pinta apilados en %."""
    return por_dependencia(db, actor, anio, modo, centro_gestor_ids)


# --------------------------------------------------------------------------- detalle
def _f(d: Decimal | None) -> float | None:
    return None if d is None else float(d)


def detalle(db: Session, actor: ActorCtx, anio: int, modo: str, *,
            centro_gestor_ids: list[uuid.UUID] | None = None, eje_id: uuid.UUID | None = None,
            color: str | None = None) -> dict:
    validar_modo(modo)
    if color is not None and color not in ce.COLORES:
        raise ApiError(422, "VALIDACION", "Color inválido", {"color": f"Debe ser uno de: {', '.join(ce.COLORES)}"})
    filas = universo(db, actor, anio, centro_gestor_ids=centro_gestor_ids,
                     eje_ids=[eje_id] if eje_id else None)
    out = []
    for f in filas:
        valor, col = f.evaluar(modo)
        if color and col != color:
            continue
        out.append({"indicador_id": f.ind.id, "nombre": f.ind.nombre, "programa_id": f.prog.id,
                    "programa": f"{f.prog.clave} — {f.prog.nombre}", "dependencia": f.cg.nombre,
                    "eje": f.eje.nombre if f.eje else None,
                    "algoritmo": f.ind.algoritmo.value if f.ind.algoritmo else None,
                    "meta_anual": _f(f.meta_num), "sumatoria_a": _f(f.res.sumatoria_a),
                    "sumatoria_b": _f(f.res.sumatoria_b), "cumplimiento_obtenido": _f(f.res.cumplimiento),
                    "cumplimiento": _f(valor), "color": col})
    return {"anio": anio, "tipo_cumplimiento": modo, "indicadores": out}


# --------------------------------------------------------------------------- selectores
def opciones(db: Session, actor: ActorCtx) -> dict:
    """Lo que el usuario puede elegir en los filtros: solo centros gestores/programas/ejes de su
    alcance, y los años con metas en sus indicadores."""
    alcance = programas_en_alcance(db, actor)
    if not alcance:
        return {"anios": [], "centros_gestores": [], "ejes": [], "programas": []}
    progs = list(db.scalars(select(Programa).where(Programa.id.in_(alcance))
                            .order_by(Programa.clave)))
    cgs = db.scalars(select(CentroGestor).where(CentroGestor.id.in_({p.centro_gestor_id for p in progs}))
                     .order_by(CentroGestor.clave))
    ejes = db.scalars(select(Eje).where(Eje.id.in_(
        select(Subtema.eje_id).where(Subtema.id.in_({p.subtema_id for p in progs if p.subtema_id}))))
        .order_by(Eje.clave))
    anios = sorted(set(db.scalars(
        select(MetaAnual.anio).join(Indicador, Indicador.id == MetaAnual.indicador_id)
        .join(ElementoMatriz, ElementoMatriz.id == Indicador.elemento_matriz_id)
        .where(ElementoMatriz.programa_id.in_(alcance)))), reverse=True)
    return {"anios": anios,
            "centros_gestores": [{"id": c.id, "clave": c.clave, "nombre": c.nombre} for c in cgs],
            "ejes": [{"id": e.id, "clave": e.clave, "nombre": e.nombre} for e in ejes],
            "programas": [{"id": p.id, "clave": p.clave, "nombre": p.nombre,
                           "centro_gestor_id": p.centro_gestor_id} for p in progs]}


def programa_exportable(db: Session, actor: ActorCtx, centro_gestor_id: uuid.UUID,
                        programa_id: uuid.UUID) -> tuple[Programa, CentroGestor]:
    """Validación de las exportaciones: el programa elegido debe estar en el alcance del usuario (403
    si no; aquí el usuario eligió un programa concreto, a diferencia de los conteos, que dan 0) y
    pertenecer al centro gestor elegido."""
    p = db.get(Programa, programa_id)
    if p is None:
        raise ApiError(404, "PROGRAMA_NO_ENCONTRADO", "Programa no encontrado")
    if p.id not in programas_en_alcance(db, actor):
        raise ApiError(403, "PROGRAMA_NO_ASIGNADO", "No tienes asignado este programa")
    if p.centro_gestor_id != centro_gestor_id:
        raise ApiError(422, "VALIDACION", "El programa no pertenece al centro gestor elegido",
                       {"programa_id": "No pertenece al centro gestor"})
    return p, db.get(CentroGestor, p.centro_gestor_id)
