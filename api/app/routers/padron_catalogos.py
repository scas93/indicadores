"""Fase 5, parte 1 — catálogos del Padrón. Tipos permitidos: padron y administrador (validado en el servidor)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ActorCtx, actor_con_tipo
from ..schemas import CapturaApoyoIn, EliminarLoteIn, PadronCatalogoIn
from ..services import padron_beneficiarios  # noqa: F401  (registra Beneficiarios en CATALOGOS)
from ..services import padron_catalogos as svc

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(prefix="/api", tags=["padron-catalogos"])
_actor = actor_con_tipo("padron_catalogos")


def _montar(cat: svc.Cat) -> None:
    base, ent = f"/{cat.ruta}", cat.entidad

    def filtros(clave, nombre, programa_id, apoyo_id, estado_id, municipio_id, curp) -> dict:
        return {"clave": clave, "nombre": nombre, "programa_id": programa_id, "apoyo_id": apoyo_id,
                "estado_id": estado_id, "municipio_id": municipio_id, "curp": curp}

    @router.get(base, name=f"listar_{ent}")
    def listar(clave: str | None = None, nombre: str | None = None, programa_id: uuid.UUID | None = None,
               apoyo_id: uuid.UUID | None = None, estado_id: uuid.UUID | None = None,
               municipio_id: uuid.UUID | None = None, curp: str | None = None,
               actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
        return cat.listar(svc.Ctx(db, actor), filtros(clave, nombre, programa_id, apoyo_id, estado_id, municipio_id, curp))

    @router.get(f"{base}/exportar", name=f"exportar_{ent}")
    def exportar(clave: str | None = None, nombre: str | None = None, programa_id: uuid.UUID | None = None,
                 apoyo_id: uuid.UUID | None = None, estado_id: uuid.UUID | None = None,
                 municipio_id: uuid.UUID | None = None, curp: str | None = None,
                 actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
        datos = cat.exportar(svc.Ctx(db, actor), filtros(clave, nombre, programa_id, apoyo_id, estado_id, municipio_id, curp))
        return Response(datos, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{ent}.xlsx"'})

    @router.post(base, status_code=201, name=f"crear_{ent}")
    def crear(body: PadronCatalogoIn, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
        ctx = svc.Ctx(db, actor)
        o = cat.crear(ctx, body.model_dump(exclude_unset=True))
        db.commit()
        return cat.fila(ctx, o)

    @router.patch(f"{base}/{{id}}", name=f"editar_{ent}")
    def editar(id: uuid.UUID, body: PadronCatalogoIn, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
        ctx = svc.Ctx(db, actor)
        o = cat.editar(ctx, id, body.model_dump(exclude_unset=True))
        db.commit()
        return cat.fila(ctx, o)

    @router.post(f"{base}/eliminar-lote", name=f"eliminar_lote_{ent}")
    def eliminar_lote(body: EliminarLoteIn, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
        r = cat.eliminar_lote(svc.Ctx(db, actor), body.ids)
        db.commit()
        return r

    @router.delete(f"{base}/{{id}}", status_code=204, name=f"eliminar_{ent}")
    def eliminar(id: uuid.UUID, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
        cat.eliminar(svc.Ctx(db, actor), id)
        db.commit()
        return Response(status_code=204)


for _cat in svc.CATALOGOS.values():
    _montar(_cat)


@router.get("/padron/programas")
def programas(actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    """Selector de programa de Apoyos: solo los programas activos asignados al usuario."""
    return svc.programas_disponibles(svc.Ctx(db, actor))


@router.get("/geo/estados")
def estados(actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return svc.estados(svc.Ctx(db, actor))


# --- Fase 4.2: autocompletado de beneficiarios y captura de apoyos ---------------------------------------
@router.get("/beneficiarios-buscar")
def buscar_beneficiarios(q: str | None = None, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return padron_beneficiarios.buscar(svc.Ctx(db, actor), q)


@router.get("/padron/contexto")
def contexto(actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return padron_beneficiarios.contexto(svc.Ctx(db, actor))


@router.get("/padron/capturas")
def capturas_del_dia(actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    return padron_beneficiarios.capturas_del_dia(svc.Ctx(db, actor))


@router.get("/padron/capturas/calculo")
def calculo(beneficiario_id: uuid.UUID, fecha_entrega: date | None = None, actor: ActorCtx = Depends(_actor),
            db: Session = Depends(get_db)):
    return padron_beneficiarios.calculo(svc.Ctx(db, actor), beneficiario_id, fecha_entrega)


@router.post("/padron/capturas", status_code=201)
def crear_captura(body: CapturaApoyoIn, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    r = padron_beneficiarios.crear_captura(svc.Ctx(db, actor), body.model_dump(exclude_unset=True))
    db.commit()
    return r


@router.delete("/padron/capturas/{id}", status_code=204)
def eliminar_captura(id: uuid.UUID, actor: ActorCtx = Depends(_actor), db: Session = Depends(get_db)):
    padron_beneficiarios.eliminar_captura(svc.Ctx(db, actor), id)
    db.commit()
    return Response(status_code=204)
