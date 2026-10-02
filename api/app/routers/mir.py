import uuid
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..schemas import AvancesGuardarIn, ElementoIn, IndicadorIn
from ..services import avances as av
from ..services import descargas
from ..services import mir as svc

router = APIRouter(prefix="/api", tags=["mir"])
_inicio = actor_con_tipo("inicio")


def hoy_actual() -> date:
    """Dependencia para poder fijar la fecha en pruebas (tolerancia de meses)."""
    return av.hoy_local()


# --- matriz --------------------------------------------------------------------
@router.get("/programas/{id}/matriz")
def matriz(id: uuid.UUID, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    r = svc.obtener(db, actor, id)
    db.commit()  # primera entrada: crea Fin y Propósito vacíos
    return r


@router.post("/programas/{id}/matriz/componentes", status_code=201)
def crear_componente(id: uuid.UUID, body: ElementoIn, actor: ActorCtx = Depends(_inicio),
                     db: Session = Depends(get_db)):
    r = svc.crear_componente(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.post("/elementos-matriz/{id}/actividades", status_code=201)
def crear_actividad(id: uuid.UUID, body: ElementoIn, actor: ActorCtx = Depends(_inicio),
                    db: Session = Depends(get_db)):
    r = svc.crear_actividad(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.patch("/elementos-matriz/{id}")
def editar_elemento(id: uuid.UUID, body: ElementoIn, actor: ActorCtx = Depends(_inicio),
                    db: Session = Depends(get_db)):
    r = svc.editar_elemento(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.delete("/elementos-matriz/{id}")
def eliminar_elemento(id: uuid.UUID, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    r = svc.eliminar_elemento(db, actor, id)
    db.commit()
    return r


@router.post("/elementos-matriz/{id}/indicadores", status_code=201)
def crear_indicador(id: uuid.UUID, body: IndicadorIn, actor: ActorCtx = Depends(_inicio),
                    db: Session = Depends(get_db)):
    r = svc.crear_indicador(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.patch("/indicadores/{id}")
def editar_indicador(id: uuid.UUID, body: IndicadorIn, actor: ActorCtx = Depends(_inicio),
                     db: Session = Depends(get_db)):
    r = svc.editar_indicador(db, actor, id, body.model_dump(exclude_unset=True))
    db.commit()
    return r


# --- captura de avances ------------------------------------------------------------
@router.get("/programas/{id}/captura-avances")
def captura(id: uuid.UUID, actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    return av.listar(db, actor, id)


@router.get("/indicadores/{id}/avances")
def rejilla(id: uuid.UUID, anio: int | None = None, actor: ActorCtx = Depends(_inicio),
            db: Session = Depends(get_db), hoy: date = Depends(hoy_actual)):
    return av.rejilla(db, actor, id, anio, hoy)


@router.post("/indicadores/{id}/avances/calcular")
def calcular_avances(id: uuid.UUID, body: AvancesGuardarIn, actor: ActorCtx = Depends(_inicio),
                     db: Session = Depends(get_db)):
    """Vista previa del cumplimiento y el semáforo con los valores capturados (no guarda nada)."""
    return av.calcular(db, actor, id, [m.model_dump() for m in body.meses])


@router.put("/indicadores/{id}/avances")
def guardar_avances(id: uuid.UUID, body: AvancesGuardarIn, anio: int, actor: ActorCtx = Depends(_inicio),
                    db: Session = Depends(get_db), hoy: date = Depends(hoy_actual)):
    r = av.guardar(db, actor, id, anio, [m.model_dump() for m in body.meses], hoy)
    db.commit()
    return r


def _pdf(contenido: bytes, nombre: str) -> Response:
    return Response(contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/programas/{id}/matriz/descarga")
def descargar_matriz(id: uuid.UUID, tipo: str = "resultados", anio: int | None = None,
                     actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db)):
    """PDF: tipo = resultados (Matriz de Indicadores de Resultados) | cumplimiento (Matriz de Cumplimiento)."""
    return _pdf(*descargas.matriz(db, actor, id, tipo, anio))


@router.get("/indicadores/{id}/exportar")
def exportar_ficha(id: uuid.UUID, formato: str = "fn", anio: int | None = None,
                   actor: ActorCtx = Depends(_inicio), db: Session = Depends(get_db),
                   hoy: date = Depends(hoy_actual)):
    """PDF: formato = fn (Ficha Narrativa) | fa (Ficha de Avance)."""
    return _pdf(*descargas.ficha(db, actor, id, formato, anio, hoy))
