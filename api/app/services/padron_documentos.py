"""Fase 4.3b — documentos de beneficiarios y Reporte Documentos.

El archivo se alcanza SIEMPRE desde su fila `DocumentoBeneficiario` (la Session ya filtra por municipio) y la llave
lleva el municipio; no existe URL pública."""
import uuid

from sqlalchemy import func, select

from .. import validators_documentos as vdoc
from ..errors import ApiError
from ..models import Beneficiario, Colonia, DocumentoBeneficiario
from .. import validators_padron_estadisticas as vpe
from .documentos_storage import obtener_almacen
from .padron_catalogos import Ctx, _como, _texto


def _beneficiario(ctx: Ctx, beneficiario_id: uuid.UUID) -> Beneficiario:
    b = ctx.db.get(Beneficiario, beneficiario_id)
    if b is None:
        raise ApiError(404, "NO_ENCONTRADO", "Beneficiario no encontrado")
    return b


def fila(d: DocumentoBeneficiario) -> dict:
    return {"id": d.id, "beneficiario_id": d.beneficiario_id, "tipo": d.tipo, "titulo": d.titulo,
            "observaciones": d.observaciones, "nombre_archivo": d.nombre_archivo, "content_type": d.content_type,
            "tamano": d.tamano, "fecha_alta": d.created_at.date().isoformat()}


def listar(ctx: Ctx, beneficiario_id: uuid.UUID) -> list[dict]:
    _beneficiario(ctx, beneficiario_id)
    return [fila(d) for d in ctx.db.scalars(select(DocumentoBeneficiario).where(
        DocumentoBeneficiario.beneficiario_id == beneficiario_id).order_by(DocumentoBeneficiario.created_at))]


def subir(ctx: Ctx, beneficiario_id: uuid.UUID, tipo: str | None, observaciones: str | None,
          nombre_archivo: str | None, contenido: bytes) -> dict:
    b = _beneficiario(ctx, beneficiario_id)
    tipo = vdoc.validar_tipo_documento(tipo)
    mime, ext = vdoc.validar_archivo(contenido)
    almacen = obtener_almacen()  # sin bucket: 503 antes de tocar nada
    id_ = uuid.uuid4()
    llave = vdoc.llave(ctx.actor.municipio_id, b.id, id_, ext)
    almacen.guardar(llave, contenido, mime)
    try:
        d = DocumentoBeneficiario(id=id_, beneficiario_id=b.id, tipo=tipo, titulo=vdoc.TIPOS[tipo],
                                  observaciones=_texto(observaciones), llave=llave,
                                  nombre_archivo=vdoc.nombre_seguro(nombre_archivo), content_type=mime, tamano=len(contenido))
        ctx.db.add(d)
        ctx.db.flush()
        ctx.bitacora("documento_beneficiario", "crear", d.id, {"curp": b.curp, "tipo": tipo})
    except Exception:
        almacen.borrar(llave)  # no dejar un archivo sin fila
        raise
    return fila(d)


def obtener(ctx: Ctx, beneficiario_id: uuid.UUID, documento_id: uuid.UUID) -> DocumentoBeneficiario:
    d = ctx.db.get(DocumentoBeneficiario, documento_id)  # filtrado por municipio
    if d is None or d.beneficiario_id != beneficiario_id or not vdoc.llave_es_de(d.llave, ctx.actor.municipio_id):
        raise ApiError(404, "NO_ENCONTRADO", "Documento no encontrado")
    return d


def leer(ctx: Ctx, beneficiario_id: uuid.UUID, documento_id: uuid.UUID) -> tuple[DocumentoBeneficiario, bytes]:
    d = obtener(ctx, beneficiario_id, documento_id)
    return d, obtener_almacen().leer(d.llave)


def borrar(ctx: Ctx, beneficiario_id: uuid.UUID, documento_id: uuid.UUID) -> None:
    d = obtener(ctx, beneficiario_id, documento_id)
    obtener_almacen().borrar(d.llave)  # si el bucket falla, la fila se queda y se puede reintentar
    ctx.bitacora("documento_beneficiario", "eliminar", d.id, {"tipo": d.tipo})
    ctx.db.delete(d)
    ctx.db.flush()


def borrar_de_beneficiario(ctx: Ctx, beneficiario_id: uuid.UUID) -> int:
    """Quita los archivos y las filas de los documentos de un beneficiario que se va a borrar."""
    docs = list(ctx.db.scalars(select(DocumentoBeneficiario).where(DocumentoBeneficiario.beneficiario_id == beneficiario_id)))
    if not docs:
        return 0
    almacen = obtener_almacen()
    for d in docs:
        almacen.borrar(d.llave)
        ctx.db.delete(d)
    ctx.db.flush()
    return len(docs)


# --------------------------------------------------------------------------- Reporte Documentos
ENCABEZADOS_REPORTE = ["CURP", "Nombre", "Estado", "Municipio", "Localidad", "Colonia", "Tel.", "Correo"]
TITULO_REPORTE = "REPORTE FALTA DE DOCUMENTOS"


def reporte(ctx: Ctx, f: dict) -> dict:
    """Todos los beneficiarios del municipio (sin límite por programa) a los que les falta el documento pedido."""
    from ..models import CatalogoMunicipio, GeografiaEstado
    faltante = vdoc.filtro_faltante(f.get("faltante"))
    stmt = _como(_como(select(Beneficiario), Beneficiario.curp, f.get("curp")), Beneficiario.nombre, f.get("nombre"))
    bens = list(ctx.db.scalars(stmt.order_by(Beneficiario.nombre, Beneficiario.curp)))
    presentes: dict[uuid.UUID, set[str]] = {}
    for bid, tipo in ctx.db.execute(select(DocumentoBeneficiario.beneficiario_id, DocumentoBeneficiario.tipo)):
        presentes.setdefault(bid, set()).add(tipo)
    bens = [b for b in bens if vdoc.le_falta(presentes.get(b.id, ()), faltante)]
    ids = {x for b in bens for x in (b.municipio_geo_id, b.localidad_id) if x}
    geo = {c.id: c.nombre for c in ctx.db.scalars(select(CatalogoMunicipio).where(CatalogoMunicipio.id.in_(ids)))} if ids else {}
    estados = {e.id: e.nombre for e in ctx.db.scalars(select(GeografiaEstado))}
    cols = {c.id: c for c in ctx.db.scalars(select(Colonia))}
    filas = []
    for b in bens:
        c = cols.get(b.colonia_id)
        filas.append([b.curp, b.nombre, estados.get(b.estado_id) or "", geo.get(b.municipio_geo_id) or "", geo.get(b.localidad_id) or "",
                      vpe.etiqueta_colonia(c.clave if c else None, c.nombre if c else None, b.colonia), b.telefono or "", b.correo or ""])
    return {"titulo": TITULO_REPORTE, "faltante": faltante, "total": len(filas), "encabezados": ENCABEZADOS_REPORTE, "filas": filas}


def exportar_reporte(ctx: Ctx, f: dict) -> tuple[bytes, str]:
    from .padron_estadisticas import _BORDE, _encabezado, _bytes
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    t = reporte(ctx, f)
    wb = Workbook()
    ws = wb.active
    ws.title = "Falta de documentos"
    ws.append(t["encabezados"])
    for c in ws[1]:
        _encabezado(c)
    ws.row_dimensions[1].height = 30
    for fila_ in t["filas"]:
        ws.append(fila_)
        for c in ws[ws.max_row]:
            c.border, c.alignment = _BORDE, Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    for i in range(1, len(t["encabezados"]) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 24
    return _bytes(wb), "reporte_falta_documentos.xlsx"
