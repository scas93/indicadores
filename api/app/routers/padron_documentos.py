"""Fase 4.3b — documentos de un beneficiario. Mismo permiso que el catálogo de Beneficiarios (padron y administrador).
Subida y descarga siempre a través de la API, con sesión vigente; no hay URL pública."""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Response, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..services import padron_catalogos as cat
from ..services import padron_documentos as svc
from ..validators_documentos import MAX_BYTES

router = APIRouter(prefix="/api/beneficiarios/{beneficiario_id}/documentos", tags=["padron-documentos"])
_actor = actor_con_tipo("padron_catalogos")


@router.get("")
def listar(beneficiario_id: uuid.UUID, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return svc.listar(cat.Ctx(db, actor), beneficiario_id)


@router.post("", status_code=201)
async def subir(beneficiario_id: uuid.UUID, archivo: UploadFile, tipo: str = Form(""), observaciones: str = Form(""),
                actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    contenido = await archivo.read(MAX_BYTES + 1)  # un byte de más basta para saber que se excedió
    ctx = cat.Ctx(db, actor)
    r = svc.subir(ctx, beneficiario_id, tipo, observaciones, archivo.filename, contenido)
    db.commit()
    return r


@router.get("/{documento_id}/archivo")
def descargar(beneficiario_id: uuid.UUID, documento_id: uuid.UUID, descargar: bool = False,
              actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    d, contenido = svc.leer(cat.Ctx(db, actor), beneficiario_id, documento_id)
    modo = "attachment" if descargar else "inline"
    return Response(contenido, media_type=d.content_type, headers={
        "Content-Disposition": f"{modo}; filename*=UTF-8''{quote(d.nombre_archivo)}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/{documento_id}", status_code=204)
def borrar(beneficiario_id: uuid.UUID, documento_id: uuid.UUID, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    svc.borrar(cat.Ctx(db, actor), beneficiario_id, documento_id)
    db.commit()
