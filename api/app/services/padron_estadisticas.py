"""Fase 4.3a — Estadísticas del Padrón: dashboard, detalles (detallado / concentrado) y comparativo.

Todo se calcula sobre las CAPTURAS de apoyo (no sobre beneficiarios distintos), acotadas a los programas que el usuario
tiene asignados. La consulta trae las filas ya filtradas y las reglas de agrupación viven en
`validators_padron_estadisticas` (funciones puras)."""
import io
import uuid
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import extract, func, select
from sqlalchemy.orm import aliased

from .. import validators_padron as vpd
from .. import validators_padron_estadisticas as vpe
from ..models import (Apoyo, Beneficiario, CapturaApoyo, CatalogoMunicipio, CentroGestor, Colonia, DescripcionApoyo,
                      GeografiaEstado, Programa)
from .padron_beneficiarios import hoy
from .padron_catalogos import Ctx


def _filtros(ctx: Ctx, f: dict):
    """Condiciones comunes. Los programas pedidos se cruzan con los asignados: uno ajeno simplemente no cuenta."""
    cond = []
    pedidos = set(f.get("programa_ids") or [])
    if ctx.visibles is not None:
        permitidos = ctx.visibles if not pedidos else (ctx.visibles & pedidos)
        cond.append(CapturaApoyo.programa_id.in_(permitidos or [uuid.UUID(int=0)]))
    elif pedidos:
        cond.append(CapturaApoyo.programa_id.in_(pedidos))
    if f.get("apoyo_id"):
        cond.append(CapturaApoyo.apoyo_id == f["apoyo_id"])
    if f.get("descripcion_apoyo_id"):
        cond.append(CapturaApoyo.descripcion_apoyo_id == f["descripcion_apoyo_id"])
    if f.get("estado_id"):
        cond.append(Beneficiario.estado_id == f["estado_id"])
    if f.get("municipio_id"):
        cond.append(Beneficiario.municipio_geo_id == f["municipio_id"])
    if f.get("localidad_id"):
        cond.append(Beneficiario.localidad_id == f["localidad_id"])
    if f.get("curp"):
        cond.append(func.upper(Beneficiario.curp) == f["curp"].strip().upper())
    if f.get("nombre"):
        cond.append(func.lower(Beneficiario.nombre).like(f"%{f['nombre'].strip().lower()}%"))
    if f.get("fecha_ini"):
        cond.append(CapturaApoyo.fecha_entrega >= f["fecha_ini"])
    if f.get("fecha_fin"):
        cond.append(CapturaApoyo.fecha_entrega <= f["fecha_fin"])
    if f.get("anio_ini"):
        cond.append(extract("year", CapturaApoyo.fecha_entrega) >= f["anio_ini"])
    if f.get("anio_fin"):
        cond.append(extract("year", CapturaApoyo.fecha_entrega) <= f["anio_fin"])
    return cond


def _filas(ctx: Ctx, f: dict) -> list[dict]:
    """Una fila por captura con todo lo que los reportes muestran o agrupan."""
    nivel, grupo = aliased(CatalogoMunicipio), aliased(CatalogoMunicipio)
    muni, loc = aliased(CatalogoMunicipio), aliased(CatalogoMunicipio)
    q = (select(CapturaApoyo, Beneficiario, Apoyo.nombre, DescripcionApoyo.nombre, Programa.clave, Programa.nombre,
                CentroGestor.nombre, nivel.nombre, grupo.nombre, GeografiaEstado.nombre, muni, loc.nombre,
                Colonia.clave, Colonia.nombre)
         .join(Beneficiario, Beneficiario.id == CapturaApoyo.beneficiario_id)
         .join(Apoyo, Apoyo.id == CapturaApoyo.apoyo_id)
         .join(Programa, Programa.id == CapturaApoyo.programa_id)
         .join(CentroGestor, CentroGestor.id == Programa.centro_gestor_id)
         .outerjoin(DescripcionApoyo, DescripcionApoyo.id == CapturaApoyo.descripcion_apoyo_id)
         .outerjoin(nivel, nivel.id == CapturaApoyo.nivel_socioeconomico_id)
         .outerjoin(grupo, grupo.id == CapturaApoyo.grupo_edad_id)
         .outerjoin(GeografiaEstado, GeografiaEstado.id == Beneficiario.estado_id)
         .outerjoin(muni, muni.id == Beneficiario.municipio_geo_id)
         .outerjoin(loc, loc.id == Beneficiario.localidad_id)
         .outerjoin(Colonia, Colonia.id == Beneficiario.colonia_id)
         .where(*_filtros(ctx, f))
         .order_by(CapturaApoyo.fecha_entrega, CapturaApoyo.created_at))
    return [{
        "captura": c, "beneficiario": b, "apoyo": ap, "descripcion": desc, "programa": f"{pc} — {pn}", "centro_gestor": cg,
        "nivel": niv, "grupo": gr, "estado": est, "municipio": m.nombre if m else None, "localidad": lo,
        "colonia": vpe.etiqueta_colonia(ccl, cnom, b.colonia),
    } for c, b, ap, desc, pc, pn, cg, niv, gr, est, m, lo, ccl, cnom in ctx.db.execute(q).all()]


# --------------------------------------------------------------------------- 1) dashboard
def dashboard(ctx: Ctx, f: dict) -> dict:
    ini, fin = vpe.validar_rango_fechas(f.get("fecha_ini"), f.get("fecha_fin"), hoy())
    filas = _filas(ctx, {**f, "fecha_ini": ini, "fecha_fin": fin})
    lista = lambda pares: [{"nombre": n, "total": t} for n, t in pares]
    return {
        "total": len(filas), "fecha_ini": ini, "fecha_fin": fin,
        "por_localidad": lista(vpe.top_n(vpe.contar((r["localidad"] for r in filas), vpe.SIN_LOCALIDAD),
                                         excluir=[vpe.SIN_LOCALIDAD])),
        "genero": vpe.conteo_genero(r["beneficiario"].genero for r in filas),
        "por_grupo_edad": lista(vpe.contar((r["grupo"] for r in filas), vpe.SIN_GRUPO)),
        "por_nivel": lista(vpe.contar((r["nivel"] for r in filas), vpe.SIN_NIVEL)),
        "por_apoyo": lista(vpe.contar((r["apoyo"] for r in filas), "Sin apoyo")),
    }


# --------------------------------------------------------------------------- 2) detalles
ENCABEZADOS_DETALLADO = ["CURP", "Nombre", "Estado", "Municipio", "Localidad", "Colonia", "Edad", "Grupo Edad",
                         "Nivel Socioeconómico", "Apoyo", "Descrip.Apoyo", "Programa", "Fecha de Entrega",
                         "Centro Gestor", "Cantidad", "Observación"]


def _fila_detallada(r: dict) -> list:
    c, b = r["captura"], r["beneficiario"]
    return [b.curp, b.nombre, r["estado"], r["municipio"], r["localidad"], r["colonia"], c.edad, r["grupo"],
            r["nivel"], r["apoyo"], r["descripcion"], r["programa"], c.fecha_entrega.isoformat(), r["centro_gestor"],
            c.cantidad, c.observaciones]


def detallado(ctx: Ctx, f: dict) -> dict:
    ini, fin = vpe.validar_rango_fechas(f.get("fecha_ini"), f.get("fecha_fin"), hoy())
    filas = _filas(ctx, {**f, "fecha_ini": ini, "fecha_fin": fin, "anio_ini": None, "anio_fin": None})
    return {"tipo": "detallado", "titulo": "DETALLADO PADRON BENEFICIARIO", "total": len(filas),
            "encabezados": ENCABEZADOS_DETALLADO, "filas": [_fila_detallada(r) for r in filas]}


def concentrado(ctx: Ctx, f: dict) -> dict:
    """Ficha de UN beneficiario (exige su CURP) y cuántos apoyos recibió por programa, apoyo y año."""
    curp = vpe.validar_curp_concentrado(f.get("curp"))
    b = ctx.db.scalar(select(Beneficiario).where(func.upper(Beneficiario.curp) == curp))
    vpe.validar_curp_concentrado(curp, existe=b is not None)
    actual = hoy().year
    ini, fin = vpe.validar_rango_anios(f.get("anio_ini"), f.get("anio_fin"), actual)
    anios = vpe.anios_del_rango(ini, fin)
    filas = _filas(ctx, {**f, "curp": curp, "fecha_ini": None, "fecha_fin": None, "anio_ini": ini, "anio_fin": fin})
    por = vpe.apoyos_por_anio(((f"{r['programa']}\x00{r['apoyo']}", r["captura"].fecha_entrega.year) for r in filas), anios)
    beneficio = [{"programa": k.split("\x00")[0], "apoyo": k.split("\x00")[1], "anios": v} for k, v in sorted(por.items())]
    ultimo = max(filas, key=lambda r: (r["captura"].fecha_entrega, r["captura"].created_at), default=None)
    edad = vpd.calcular_edad(b.fecha_nacimiento, hoy()) if b.fecha_nacimiento else None
    grupos = [(g.id, g.datos["edad_min"], g.datos.get("edad_max")) for g in ctx.db.scalars(
        select(CatalogoMunicipio).where(CatalogoMunicipio.tipo == "grupo_edad")) if (g.datos or {}).get("edad_min") is not None]
    gid = vpd.grupo_de_edad(edad, grupos)
    g = ctx.db.get(CatalogoMunicipio, gid) if gid else None
    loc = ctx.db.get(CatalogoMunicipio, b.localidad_id) if b.localidad_id else None
    return {"tipo": "concentrado", "anios": anios, "beneficiario": {
        "id": b.id, "curp": b.curp, "nombre": b.nombre, "edad_actual": edad, "genero": vpd.GENEROS.get(b.genero),
        "grupo_edad_actual": g.nombre if g else None, "localidad": loc.nombre if loc else None,
        "nivel_socioeconomico": ultimo["nivel"] if ultimo else None},
        "beneficio": beneficio, "documentos": []}  # los documentos llegan en la 4.3b


def detalles(ctx: Ctx, f: dict) -> dict:
    return concentrado(ctx, f) if f.get("tipo") == "concentrado" else detallado(ctx, f)


# --------------------------------------------------------------------------- 3) comparativo
def comparativo(ctx: Ctx, f: dict) -> dict:
    ini, fin = vpe.validar_rango_anios(f.get("anio_ini"), f.get("anio_fin"), hoy().year)
    anios = vpe.anios_del_rango(ini, fin)
    filas = _filas(ctx, {**f, "fecha_ini": None, "fecha_fin": None, "anio_ini": ini, "anio_fin": fin})
    return {"anios": anios, "localidades": vpe.comparativo_top(
        ((r["localidad"], r["captura"].fecha_entrega.year) for r in filas), anios)}


# --------------------------------------------------------------------------- exportar (mismo estilo que la Fase 3)
_GRIS = PatternFill("solid", fgColor="BBBBBB")
_BORDE = Border(*(Side(style="thin"),) * 4)
_CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _encabezado(c) -> None:
    c.fill, c.font, c.alignment, c.border = _GRIS, Font(bold=True), _CENTRO, _BORDE


def _bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def exportar_detalles(ctx: Ctx, f: dict) -> tuple[bytes, str]:
    t = detalles(ctx, f)
    wb = Workbook()
    ws = wb.active
    if t["tipo"] == "detallado":
        ws.title = "Detallado"
        ws.append(t["encabezados"])
        for c in ws[1]:
            _encabezado(c)
        ws.row_dimensions[1].height = 45
        for fila in t["filas"]:
            ws.append(fila)
            for c in ws[ws.max_row]:
                c.border, c.alignment = _BORDE, Alignment(vertical="center", wrap_text=True)
        n, nombre = len(t["encabezados"]), "detallado_padron_beneficiario.xlsx"
        ws.freeze_panes = "A2"
    else:
        ws.title = "Concentrado"
        b = t["beneficiario"]
        for k, v in (("Beneficiario", b["nombre"]), ("CURP", b["curp"]), ("Edad Actual", b["edad_actual"]), ("Genero", b["genero"]),
                     ("Grupo Edad Actual", b["grupo_edad_actual"]), ("Localidad", b["localidad"]),
                     ("Nivel Socioeconomico (ultimo registro)", b["nivel_socioeconomico"])):
            ws.append([k, v])
            _encabezado(ws.cell(ws.max_row, 1))
            ws.cell(ws.max_row, 2).border = _BORDE
        ws.append([])
        ws.append(["Programa", "Apoyo", *t["anios"]])
        for c in ws[ws.max_row]:
            _encabezado(c)
        for r in t["beneficio"]:
            ws.append([r["programa"], r["apoyo"], *[r["anios"][a] for a in t["anios"]]])
            for c in ws[ws.max_row]:
                c.border = _BORDE
        n, nombre = 2 + len(t["anios"]), "concentrado_padron_beneficiario.xlsx"
    for i in range(1, n + 1):
        ws.column_dimensions[get_column_letter(i)].width = 22
    return _bytes(wb), nombre
