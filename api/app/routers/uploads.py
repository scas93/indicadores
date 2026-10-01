from fastapi import APIRouter, Depends, UploadFile

from ..deps import SesionSuperAdmin, sesion_admin
from ..services.storage import MAX_BYTES, guardar_imagen

router = APIRouter(prefix="/api/admin/uploads", tags=["admin-uploads"])


@router.post("/imagen", status_code=201)
async def subir_imagen(archivo: UploadFile, ses: SesionSuperAdmin = Depends(sesion_admin)):
    contenido = await archivo.read(MAX_BYTES + 1)
    return {"url": guardar_imagen(contenido, archivo.content_type or "")}
