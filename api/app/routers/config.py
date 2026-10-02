from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from .. import validators_usuarios as vu
from ..db import get_db
from ..deps import ActorCtx, SesionUsuario, actor_con_tipo, municipio_actual, require_tipo
from ..models import ActorTipo, Municipio
from ..schemas import ConfigEditarIn
from ..services.bitacora import registrar
from ..services.storage import MAX_BYTES, guardar_imagen

router = APIRouter(prefix="/api", tags=["config"])


def _config(m: Municipio) -> dict:
    return {"nombre": m.nombre, "logo_url": m.logo_url, "imagen_login_url": m.imagen_login_url,
            "color_boton": m.color_boton.value, "mostrar_logos": m.mostrar_logos,
            "duracion_sesion_dias": m.duracion_sesion_dias,
            "meses_avance_activos": sorted(m.meses_avance_activos or []),
            "tolerancia_semaforo": m.tolerancia_semaforo}


@router.get("/config")
def obtener(ses: SesionUsuario = Depends(require_tipo("config_ver"))):
    return _config(ses.municipio)


@router.patch("/config")
def editar(body: ConfigEditarIn, ses: SesionUsuario = Depends(require_tipo("config_ver")),
           db: Session = Depends(get_db)):
    cambios = body.model_dump(exclude_unset=True)
    # login (imagen, color, logos) -> informes y administrador; meses y tolerancia -> alcalde y administrador
    vu.validar_campos_config(ses.usuario.tipo.value, cambios)
    if "meses_avance_activos" in cambios:
        cambios["meses_avance_activos"] = vu.validar_meses_avance(cambios["meses_avance_activos"] or [])
    if "tolerancia_semaforo" in cambios:
        cambios["tolerancia_semaforo"] = vu.validar_tolerancia(cambios["tolerancia_semaforo"])
    m = ses.municipio
    for k, val in cambios.items():
        if k in ("color_boton", "mostrar_logos", "meses_avance_activos", "tolerancia_semaforo") and val is None:
            continue
        setattr(m, k, val)
    registrar(db, actor_tipo=ActorTipo.usuario, actor_id=ses.usuario.id, accion="config.editar",
              entidad="municipio", entidad_id=m.id, municipio_id=m.id,
              detalle={k: str(val) for k, val in cambios.items()})
    db.commit()
    return _config(m)


@router.post("/uploads/imagen", status_code=201)
async def subir_imagen(archivo: UploadFile, ses: SesionUsuario = Depends(require_tipo("config_ver"))):
    """Imagen de login del municipio (Configuración → Login)."""
    vu.validar_campos_config(ses.usuario.tipo.value, ["imagen_login_url"])
    contenido = await archivo.read(MAX_BYTES + 1)
    return {"url": guardar_imagen(contenido, archivo.content_type or "")}
