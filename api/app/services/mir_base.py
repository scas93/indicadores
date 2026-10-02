"""Acceso a programas y datos del programa compartidos por árbol, matriz, captura y PDFs."""
import uuid

from sqlalchemy.orm import Session

from ..deps import ActorCtx
from ..errors import ApiError
from ..models import (CentroGestor, ClasificacionProgramatica, Eje, ElementoMatriz, Estrategia,
                      Indicador, Programa, Subtema)
from .programas import visibles


def programa_accesible(db: Session, actor: ActorCtx, programa_id: uuid.UUID) -> Programa:
    """El programa debe existir en el municipio (404) y estar asignado al usuario en sesión (403),
    sin importar su tipo: administrador y alcalde ven todos, el resto solo su matriz.
    Se lee de la base en cada petición, nunca de la sesión."""
    p = db.get(Programa, programa_id)
    if p is None:
        raise ApiError(404, "PROGRAMA_NO_ENCONTRADO", "Programa no encontrado")
    ver = visibles(db, actor.tipo_usuario, actor.usuario_id)
    if ver is not None and p.id not in ver:
        raise ApiError(403, "PROGRAMA_NO_ASIGNADO", "No tienes asignado este programa")
    return p


def elemento_accesible(db: Session, actor: ActorCtx, elemento_id: uuid.UUID) -> tuple[ElementoMatriz, Programa]:
    e = db.get(ElementoMatriz, elemento_id)
    if e is None:
        raise ApiError(404, "ELEMENTO_NO_ENCONTRADO", "Elemento de la matriz no encontrado")
    return e, programa_accesible(db, actor, e.programa_id)


def indicador_accesible(db: Session, actor: ActorCtx, indicador_id: uuid.UUID
                        ) -> tuple[Indicador, ElementoMatriz, Programa]:
    i = db.get(Indicador, indicador_id)
    if i is None:
        raise ApiError(404, "INDICADOR_NO_ENCONTRADO", "Indicador no encontrado")
    e, p = elemento_accesible(db, actor, i.elemento_matriz_id)
    return i, e, p


def programa_info(db: Session, p: Programa) -> dict:
    """Datos del programa en solo lectura (modales y PDFs): eje, subtema, estrategia, centro gestor
    y nivel (clasificación programática)."""
    cg = db.get(CentroGestor, p.centro_gestor_id)
    st = db.get(Subtema, p.subtema_id) if p.subtema_id else None
    ej = db.get(Eje, st.eje_id) if st else None
    es = db.get(Estrategia, p.estrategia_id) if p.estrategia_id else None
    cl = db.get(ClasificacionProgramatica, p.clasificacion_programatica_id) \
        if p.clasificacion_programatica_id else None
    nombre = lambda o: f"{o.clave} — {o.nombre}" if o else None  # noqa: E731
    return {"id": p.id, "ejercicio_fiscal": p.ejercicio_fiscal, "clave": p.clave, "nombre": p.nombre,
            "centro_gestor": nombre(cg), "eje": nombre(ej), "subtema": nombre(st),
            "estrategia": nombre(es), "nivel": cl.nombre if cl else None}
