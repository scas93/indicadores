"""Captura mensual de avances. Sumatoria y cumplimiento nunca se guardan: se calculan al leer."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import validators_mir as vm
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import (Algoritmo, AvanceMensual, ElementoMatriz, Indicador, MetaAnual, Municipio,
                      NivelMatriz)
from . import cumplimiento as cumpl
from .bitacora import registrar
from .mir_base import indicador_accesible, programa_accesible, programa_info

ORDEN_NIVEL = {NivelMatriz.fin: 0, NivelMatriz.proposito: 1, NivelMatriz.componente: 2, NivelMatriz.actividad: 3}


def hoy_local() -> date:
    """Fecha de hoy en México (los municipios cierran mes en hora local); UTC si no hay tzdata."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Mexico_City")).date()
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).date()


def _f(d: Decimal | None) -> float | None:
    return None if d is None else float(d)


def _datos_generales(db: Session, i: Indicador, e: ElementoMatriz) -> dict:
    solo_a = i.algoritmo == Algoritmo.a
    return {"id": i.id, "nombre": i.nombre, "interpretacion": i.interpretacion, "tipo": i.tipo.value,
            "prioritario": i.prioritario, "dimension": i.dimension.value if i.dimension else None,
            "frecuencia_id": i.frecuencia_id, "unidad_medida": i.unidad_medida,
            "algoritmo": i.algoritmo.value if i.algoritmo else None, "usa_b": vm.usa_b(
                i.algoritmo.value if i.algoritmo else None), "unidad_a": i.unidad_a,
            "unidad_b": None if solo_a else i.unidad_b,
            "nivel": e.nivel.value, "numero": e.numero, "resumen_narrativo": e.resumen_narrativo,
            "anio_base": i.anio_base, "meta_administracion": _f(i.meta_administracion)}


def _anio_por_defecto(db: Session, i: Indicador, programa_ejercicio: int) -> int:
    fiscal = db.scalar(select(MetaAnual.anio).where(MetaAnual.indicador_id == i.id,
                                                    MetaAnual.es_ejercicio_fiscal.is_(True)))
    return fiscal or programa_ejercicio


def listar(db: Session, actor: ActorCtx, programa_id: uuid.UUID) -> dict:
    """Indicadores del programa con sus datos generales de solo lectura y el resultado del año
    fiscal vigente (semáforo)."""
    p = programa_accesible(db, actor, programa_id)
    filas = db.execute(select(Indicador, ElementoMatriz).join(
        ElementoMatriz, Indicador.elemento_matriz_id == ElementoMatriz.id)
        .where(ElementoMatriz.programa_id == p.id)).all()
    filas.sort(key=lambda t: (ORDEN_NIVEL[t[1].nivel], t[1].orden, t[0].created_at))
    out = []
    por_anio: dict[int, list[Indicador]] = {}
    anios = {i.id: _anio_por_defecto(db, i, p.ejercicio_fiscal) for i, _ in filas}
    for i, _ in filas:
        por_anio.setdefault(anios[i.id], []).append(i)
    resultados = {}
    for anio, inds in por_anio.items():
        resultados.update(cumpl.resultados_del_anio(db, inds, anio))
    for i, e in filas:
        out.append({**_datos_generales(db, i, e), "anio": anios[i.id],
                    **cumpl.resultado_a_dict(resultados[i.id])})
    return {"programa": programa_info(db, p), "indicadores": out}


def _filas_anio(db: Session, i: Indicador, anio: int) -> dict[int, AvanceMensual]:
    return {a.mes: a for a in db.scalars(select(AvanceMensual).where(
        AvanceMensual.indicador_id == i.id, AvanceMensual.anio == anio))}


def rejilla(db: Session, actor: ActorCtx, indicador_id: uuid.UUID, anio: int | None, hoy: date) -> dict:
    i, e, p = indicador_accesible(db, actor, indicador_id)
    anio = vm.validar_anio(anio) if anio is not None else _anio_por_defecto(db, i, p.ejercicio_fiscal)
    m = db.get(Municipio, actor.municipio_id)
    activos = list(m.meses_avance_activos or [])
    filas = _filas_anio(db, i, anio)
    usa_b = vm.usa_b(i.algoritmo.value if i.algoritmo else None)
    meses = []
    for mes in range(1, 13):
        f = filas.get(mes)
        meses.append({"mes": mes, "valor_a": _f(f.valor_a) if f else None,
                      "valor_b": _f(f.valor_b) if (f and usa_b) else None,
                      "capturable": vm.mes_capturable(anio, mes, hoy, activos, m.tolerancia_semaforo)})
    res = cumpl.evaluar_indicador(i, {mes: (f.valor_a, f.valor_b) for mes, f in filas.items()})
    metas = list(db.scalars(select(MetaAnual).where(MetaAnual.indicador_id == i.id).order_by(MetaAnual.anio)))
    meta = next((x for x in metas if x.anio == anio), None)
    anios_con_avance = set(db.scalars(select(AvanceMensual.anio).where(AvanceMensual.indicador_id == i.id)))
    return {
        "indicador": _datos_generales(db, i, e), "anio": anio,
        "anios": sorted({x.anio for x in metas} | anios_con_avance | {anio}),
        "meta": None if meta is None else {
            "valor_a_programado": _f(meta.valor_a_programado),
            "valor_b_programado": _f(meta.valor_b_programado) if usa_b else None,
            "es_ejercicio_fiscal": meta.es_ejercicio_fiscal},
        "rangos": {c: {"desde": _f(getattr(i, f"rango_{c}_desde")), "hasta": _f(getattr(i, f"rango_{c}_hasta"))}
                   for c in ("verde", "amarillo", "rojo")},
        "meses": meses, **cumpl.resultado_a_dict(res),
    }


def guardar(db: Session, actor: ActorCtx, indicador_id: uuid.UUID, anio: int, meses: list[dict],
            hoy: date) -> dict:
    """Guarda los valores de un año. Rechaza SOLO los meses que no se pueden capturar (con detalle)
    sin bloquear los demás; si no queda ninguno por guardar y hubo rechazos, 422."""
    i, e, p = indicador_accesible(db, actor, indicador_id)
    anio = vm.validar_anio(anio)
    algoritmo = i.algoritmo.value if i.algoritmo else None
    for m in meses:
        vm.validar_mes(m.get("mes"))
    if len({m["mes"] for m in meses}) != len(meses):
        raise ApiError(422, "MES_REPETIDO", "Hay meses repetidos", {"meses": "Meses repetidos"})
    vm.validar_avances_b(algoritmo, meses)  # solo A: B se rechaza en el servidor
    norm = [{"mes": m["mes"], "valor_a": vm.normalizar_valor(m.get("valor_a"), f"mes_{m['mes']}"),
             "valor_b": vm.normalizar_valor(m.get("valor_b"), f"mes_{m['mes']}")} for m in meses]
    filas = _filas_anio(db, i, anio)
    muni = db.get(Municipio, actor.municipio_id)
    vigentes = {mes: (f.valor_a, f.valor_b) for mes, f in filas.items()}
    # con "solo A" la B guardada de antes no es parte de la captura: se compara solo A
    if algoritmo == "a":
        for n in norm:
            n["valor_b"] = vigentes.get(n["mes"], (None, None))[1]
    aceptados, rechazados = vm.clasificar_meses(
        anio, norm, vigentes, hoy, muni.meses_avance_activos or [], muni.tolerancia_semaforo)
    if rechazados and not aceptados:
        raise ApiError(422, "MESES_NO_CAPTURABLES", "Ninguno de los meses se puede capturar",
                       {f"mes_{r.mes}": r.mensaje for r in rechazados})
    for n in aceptados:
        f = filas.get(n["mes"])
        if n["valor_a"] is None and n["valor_b"] is None:
            if f is not None:
                db.delete(f)
            continue
        if f is None:
            f = AvanceMensual(indicador_id=i.id, anio=anio, mes=n["mes"])
            db.add(f)
        f.valor_a, f.valor_b = n["valor_a"], n["valor_b"]
    db.flush()
    registrar(db, actor_tipo=actor.actor_tipo, actor_id=actor.actor_id, accion="avance.guardar",
              entidad="indicador", entidad_id=i.id, municipio_id=actor.municipio_id,
              detalle={"anio": anio, "meses_guardados": sorted(n["mes"] for n in aceptados),
                       "meses_rechazados": sorted(r.mes for r in rechazados)})
    return {"guardados": sorted(n["mes"] for n in aceptados),
            "rechazados": [{"mes": r.mes, "codigo": r.codigo, "mensaje": r.mensaje} for r in rechazados],
            "rejilla": rejilla(db, actor, indicador_id, anio, hoy)}


def calcular(db: Session, actor: ActorCtx, indicador_id: uuid.UUID, meses: list[dict]) -> dict:
    """Vista previa en vivo de la rejilla (sin guardar): mismo cálculo que al leer, para que el
    front no reimplemente sumatoria, algoritmo ni semáforo."""
    i, _, _ = indicador_accesible(db, actor, indicador_id)
    for m in meses:
        vm.validar_mes(m.get("mes"))
    por_mes = {m["mes"]: (vm.normalizar_valor(m.get("valor_a"), f"mes_{m['mes']}"),
                          vm.normalizar_valor(m.get("valor_b"), f"mes_{m['mes']}")) for m in meses}
    return cumpl.resultado_a_dict(cumpl.evaluar_indicador(i, por_mes))
