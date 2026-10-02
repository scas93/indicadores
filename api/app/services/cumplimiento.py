"""Cumplimiento y semáforo de indicadores leídos de la base. Punto único que Fase 3 reutiliza:
nada se guarda, todo se calcula aquí con `app.calculo` a partir de `avance_mensual`."""
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calculo
from ..models import AvanceMensual, Indicador


def avances_del_anio(db: Session, indicador_ids: list[uuid.UUID], anio: int
                     ) -> dict[uuid.UUID, dict[int, tuple[Decimal | None, Decimal | None]]]:
    """{indicador_id: {mes: (a, b)}} de un año, en una sola consulta."""
    out: dict = defaultdict(dict)
    if not indicador_ids:
        return out
    filas = db.scalars(select(AvanceMensual).where(
        AvanceMensual.indicador_id.in_(indicador_ids), AvanceMensual.anio == anio))
    for f in filas:
        out[f.indicador_id][f.mes] = (f.valor_a, f.valor_b)
    return out


def evaluar_indicador(ind: Indicador, meses: dict[int, tuple[Decimal | None, Decimal | None]]
                      ) -> calculo.Resultado:
    verde, amarillo, rojo = calculo.rangos_de(ind)
    algoritmo = ind.algoritmo.value if ind.algoritmo else None
    return calculo.evaluar(algoritmo, meses.values(), verde, amarillo, rojo)


def resultados_del_anio(db: Session, indicadores: list[Indicador], anio: int
                        ) -> dict[uuid.UUID, calculo.Resultado]:
    avances = avances_del_anio(db, [i.id for i in indicadores], anio)
    return {i.id: evaluar_indicador(i, avances.get(i.id, {})) for i in indicadores}


def resultado_a_dict(r: calculo.Resultado) -> dict:
    f = lambda d: None if d is None else float(d)  # noqa: E731
    return {"sumatoria_a": f(r.sumatoria_a), "sumatoria_b": f(r.sumatoria_b),
            "cumplimiento": f(r.cumplimiento), "color": r.color}
