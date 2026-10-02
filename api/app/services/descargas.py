"""Datos para los PDF: arma lo que `pdf.py` necesita a partir de la base."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import ActorCtx
from ..errors import ApiError
from ..models import ElementoMatriz, Frecuencia, Indicador, MetaAnual
from . import arbol as arbol_svc
from . import avances as av
from . import cumplimiento as cumpl
from . import mir as mir_svc
from . import pdf
from .mir_base import indicador_accesible, programa_accesible, programa_info


def _frecuencias(db: Session) -> dict[str, str]:
    return {str(f.id): f.nombre for f in db.scalars(select(Frecuencia))}


def _tipo(valor: str, validos: tuple[str, ...]) -> str:
    if valor not in validos:
        raise ApiError(422, "TIPO_INVALIDO", f"tipo debe ser uno de: {', '.join(validos)}", {"tipo": "Inválido"})
    return valor


def arbol(db: Session, actor: ActorCtx, programa_id: uuid.UUID, tipo: str) -> tuple[bytes, str]:
    tipo = _tipo(tipo, ("completo", "problemas", "objetivos"))
    data = arbol_svc.obtener(db, actor, programa_id)
    return pdf.arbol_pdf(data, tipo), f"arbol-{tipo}-{data['programa']['clave']}.pdf"


def matriz(db: Session, actor: ActorCtx, programa_id: uuid.UUID, tipo: str, anio: int | None) -> tuple[bytes, str]:
    tipo = _tipo(tipo, ("resultados", "cumplimiento"))
    p = programa_accesible(db, actor, programa_id)
    data = mir_svc.obtener(db, actor, programa_id)
    db.commit()  # puede haber creado Fin y Propósito en la primera entrada
    frec = _frecuencias(db)
    if tipo == "resultados":
        return pdf.matriz_resultados_pdf(data, frec), f"matriz-resultados-{p.clave}.pdf"
    anio = anio or p.ejercicio_fiscal
    inds = list(db.scalars(select(Indicador).join(
        ElementoMatriz, Indicador.elemento_matriz_id == ElementoMatriz.id)
        .where(ElementoMatriz.programa_id == p.id)))
    res = cumpl.resultados_del_anio(db, inds, anio)
    metas = {(m.indicador_id, m.anio): m for m in db.scalars(select(MetaAnual).where(
        MetaAnual.indicador_id.in_([i.id for i in inds]), MetaAnual.anio == anio))} if inds else {}
    resultados = {}
    for i in inds:
        d = cumpl.resultado_a_dict(res[i.id])
        meta = metas.get((i.id, anio))
        d["meta_a"] = float(meta.valor_a_programado) if meta and meta.valor_a_programado is not None else None
        d["meta_b"] = (float(meta.valor_b_programado) if meta and meta.valor_b_programado is not None
                       and i.algoritmo is not None and i.algoritmo.value != "a" else None)
        resultados[i.id] = d
    return pdf.matriz_cumplimiento_pdf(data, resultados, anio, frec), f"matriz-cumplimiento-{anio}-{p.clave}.pdf"


def ficha(db: Session, actor: ActorCtx, indicador_id: uuid.UUID, formato: str, anio: int | None,
          hoy: date) -> tuple[bytes, str]:
    formato = _tipo(formato, ("fn", "fa"))
    i, e, p = indicador_accesible(db, actor, indicador_id)
    programa = programa_info(db, p)
    elemento = mir_svc.elemento_dict(e)
    if formato == "fn":
        ind = mir_svc.indicador_dict(i, mir_svc.metas_de(db, [i.id])[i.id])
        return pdf.ficha_narrativa_pdf(programa, elemento, ind, _frecuencias(db)), f"ficha-narrativa-{i.id}.pdf"
    rej = av.rejilla(db, actor, indicador_id, anio, hoy)
    return pdf.ficha_avance_pdf(programa, elemento, rej), f"ficha-avance-{rej['anio']}-{i.id}.pdf"
