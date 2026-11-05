"""Fase 4.2 — catálogo de Beneficiarios y captura de apoyos del Padrón.

Beneficiarios usa el mismo molde que los catálogos de la parte 1 (se monta en el mismo router). La captura
(`CapturaApoyo`) liga beneficiario + programa + apoyo + fecha de entrega, de modo que las estadísticas de la 4.3
(por localidad, género, grupo de edad, nivel socioeconómico y tipo de apoyo) salen de joins directos.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import func, select

from .. import validators_padron as vpd
from ..errors import ApiError
from ..models import (Apoyo, Beneficiario, CapturaApoyo, CatalogoMunicipio, Colonia, DescripcionApoyo,
                      GeografiaEstado, Programa)
from . import padron_catalogos as base
from .padron_catalogos import CATALOGOS, USOS_EXTRA, Cat, Ctx, _como, _flush, _texto


def hoy() -> date:
    return datetime.now(vpd.ZONA_MEXICO).date()


def _cuenta(modelo, columna):
    return lambda db, id_: db.scalar(select(func.count()).select_from(modelo).where(columna == id_))


# Quién usa cada registro: ninguno de estos se borra mientras tenga capturas o beneficiarios
USOS_EXTRA["apoyo"].append(("capturas", _cuenta(CapturaApoyo, CapturaApoyo.apoyo_id)))
USOS_EXTRA["descripcion_apoyo"].append(("capturas", _cuenta(CapturaApoyo, CapturaApoyo.descripcion_apoyo_id)))
USOS_EXTRA["nivel_socioeconomico"].append(("capturas", _cuenta(CapturaApoyo, CapturaApoyo.nivel_socioeconomico_id)))
USOS_EXTRA["grupo_edad"].append(("capturas", _cuenta(CapturaApoyo, CapturaApoyo.grupo_edad_id)))
USOS_EXTRA["geo_municipio"].append(("beneficiarios", _cuenta(Beneficiario, Beneficiario.municipio_geo_id)))
USOS_EXTRA["geo_localidad"].append(("beneficiarios", _cuenta(Beneficiario, Beneficiario.localidad_id)))
USOS_EXTRA["colonia"].append(("beneficiarios", _cuenta(Beneficiario, Beneficiario.colonia_id)))
USOS_EXTRA["beneficiario"].append(("capturas", _cuenta(CapturaApoyo, CapturaApoyo.beneficiario_id)))


# --------------------------------------------------------------------------- beneficiarios
class Beneficiarios(Cat):
    ruta, entidad, modelo = "beneficiarios", "beneficiario", Beneficiario
    columnas = [("CURP", "curp"), ("Beneficiario", "nombre"), ("Fecha de nacimiento", "fecha_nacimiento"),
                ("Género", "genero_nombre"), ("CP", "cp"), ("Estado", "estado"), ("Municipio", "municipio"),
                ("Localidad", "localidad"), ("Calle", "calle"), ("Número", "numero"), ("Colonia", "colonia"),
                ("Teléfono", "telefono"), ("Correo", "correo")]

    def listar_filas(self, ctx, objs):
        ids = {x for o in objs for x in (o.municipio_geo_id, o.localidad_id) if x}
        geo = {c.id: c.nombre for c in ctx.db.scalars(select(CatalogoMunicipio).where(CatalogoMunicipio.id.in_(ids)))} if ids else {}
        estados = {e.id: e.nombre for e in ctx.db.scalars(select(GeografiaEstado))}
        return [{"id": o.id, "curp": o.curp, "nombre": o.nombre,
                 "fecha_nacimiento": o.fecha_nacimiento.isoformat() if o.fecha_nacimiento else None,
                 "genero": o.genero, "genero_nombre": vpd.GENEROS.get(o.genero, ""), "cp": o.cp,
                 "estado_id": o.estado_id, "estado": estados.get(o.estado_id),
                 "municipio_id": o.municipio_geo_id, "municipio": geo.get(o.municipio_geo_id),
                 "localidad_id": o.localidad_id, "localidad": geo.get(o.localidad_id),
                 "calle": o.calle, "numero": o.numero, "colonia": o.colonia, "colonia_id": o.colonia_id, "telefono": o.telefono,
                 "correo": o.correo, "es_ejemplo": o.es_ejemplo} for o in objs]

    def listar(self, ctx, f):
        stmt = _como(_como(select(Beneficiario), Beneficiario.curp, f.get("curp")), Beneficiario.nombre, f.get("nombre"))
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(Beneficiario.nombre, Beneficiario.curp))))

    def usos(self, ctx, o):
        return {"capturas": ctx.db.scalar(select(func.count()).select_from(CapturaApoyo).where(
            CapturaApoyo.beneficiario_id == o.id))}

    # -- validación y armado -------------------------------------------------------------------
    def _geografia(self, ctx, estado_id, municipio_id, localidad_id) -> None:
        if estado_id is not None and ctx.db.get(GeografiaEstado, estado_id) is None:
            raise ApiError(422, "JERARQUIA_INVALIDA", "Estado inválido", {"estado_id": "Estado inválido"})
        m = ctx.db.get(CatalogoMunicipio, municipio_id) if municipio_id else None
        if municipio_id and (m is None or m.tipo != "geo_municipio"):
            raise ApiError(422, "JERARQUIA_INVALIDA", "Municipio inexistente", {"municipio_id": "Municipio inválido"})
        loc = ctx.db.get(CatalogoMunicipio, localidad_id) if localidad_id else None
        if localidad_id and (loc is None or loc.tipo != "geo_localidad"):
            raise ApiError(422, "JERARQUIA_INVALIDA", "Localidad inexistente", {"localidad_id": "Localidad inválida"})
        vpd.validar_cascada_geografica(estado_id, base.estado_de_municipio(ctx, m) if m else None, municipio_id,
                                       loc.padre_id if loc else None, localidad_id)

    def _colonia(self, ctx, texto, colonia_id, municipio_id) -> tuple[str | None, uuid.UUID | None]:
        """Colonia del catálogo (se guarda su nombre y su id) o escrita a mano (solo texto)."""
        if not colonia_id:
            return _texto(texto), None
        c = ctx.db.get(Colonia, colonia_id)
        if c is None:
            raise ApiError(422, "JERARQUIA_INVALIDA", "Colonia inexistente", {"colonia": "Colonia inválida"})
        if municipio_id is not None and c.municipio_geo_id != municipio_id:
            raise ApiError(422, "JERARQUIA_INVALIDA", "La colonia no pertenece al municipio",
                           {"colonia": "No pertenece al municipio elegido"})
        return c.nombre, c.id

    def _campos(self, ctx, datos: dict, actual: Beneficiario | None) -> dict:
        def dato(k, d=None):
            return datos[k] if k in datos else (getattr(actual, d or k) if actual else None)

        curp = vpd.normalizar_curp(dato("curp"))
        nombre = vpd.validar_nombre(dato("nombre"))
        estado_id, municipio_id, localidad_id = dato("estado_id"), dato("municipio_id", "municipio_geo_id"), dato("localidad_id")
        self._geografia(ctx, estado_id, municipio_id, localidad_id)
        colonia, colonia_id = self._colonia(ctx, dato("colonia"), (datos.get("colonia_id") if "colonia_id" in datos else (
            None if "colonia" in datos else dato("colonia_id"))), municipio_id)
        stmt = select(Beneficiario.curp)
        if actual:
            stmt = stmt.where(Beneficiario.id != actual.id)
        vpd.levantar_si_curp_repetida(curp, ctx.db.scalars(stmt))
        return dict(curp=curp, nombre=nombre,
                    fecha_nacimiento=vpd.validar_fecha_nacimiento(dato("fecha_nacimiento"), hoy()),
                    genero=vpd.validar_genero(dato("genero")), cp=_texto(dato("cp")),
                    estado_id=estado_id, municipio_geo_id=municipio_id, localidad_id=localidad_id,
                    calle=_texto(dato("calle")), numero=_texto(dato("numero")), colonia=colonia, colonia_id=colonia_id,
                    telefono=_texto(dato("telefono")), correo=vpd.validar_correo(dato("correo")))

    def crear(self, ctx, datos):
        o = Beneficiario(municipio_id=ctx.actor.municipio_id, **self._campos(ctx, datos, None))
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"curp": o.curp})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        for k, v in self._campos(ctx, datos, o).items():
            setattr(o, k, v)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"curp": o.curp})
        return o

    def eliminar(self, ctx, id_):
        o = self.obtener(ctx, id_)
        vpd.validar_borrable(self.usos(ctx, o))
        curp = o.curp
        ctx.db.delete(o)
        ctx.db.flush()
        ctx.bitacora(self.entidad, "eliminar", id_, {"curp": curp})


CATALOGOS[Beneficiarios.ruta] = Beneficiarios()


def buscar(ctx: Ctx, q: str | None, limite: int = 15) -> list[dict]:
    """Autocompletado de la captura: por CURP o por nombre; devuelve la fila completa (sirve para editarla)."""
    q = (_texto(q) or "").lower()
    stmt = select(Beneficiario)
    if q:
        stmt = stmt.where(func.lower(Beneficiario.curp).like(f"%{q}%") | func.lower(Beneficiario.nombre).like(f"%{q}%"))
    return CATALOGOS["beneficiarios"].listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(Beneficiario.nombre).limit(limite))))


# --------------------------------------------------------------------------- captura
def _grupos(ctx: Ctx) -> list[vpd.Rango]:
    return [(o.id, o.datos["edad_min"], o.datos.get("edad_max")) for o in ctx.db.scalars(
        select(CatalogoMunicipio).where(CatalogoMunicipio.tipo == "grupo_edad"))
        if (o.datos or {}).get("edad_min") is not None]


def calculo(ctx: Ctx, beneficiario_id: uuid.UUID, fecha_entrega: date | None) -> dict:
    """Edad (a la fecha de entrega) y grupo de edad del beneficiario."""
    b = ctx.db.get(Beneficiario, beneficiario_id)
    if b is None:
        raise ApiError(404, "NO_ENCONTRADO", "Beneficiario no encontrado")
    edad = vpd.calcular_edad(b.fecha_nacimiento, fecha_entrega or hoy()) if b.fecha_nacimiento else None
    gid = vpd.grupo_de_edad(edad, _grupos(ctx))
    g = ctx.db.get(CatalogoMunicipio, gid) if gid else None
    return {"edad": edad, "grupo_edad_id": gid, "grupo_edad": g.nombre if g else None,
            "tiene_fecha_nacimiento": b.fecha_nacimiento is not None}


def _fila_captura(ctx: Ctx, objs: list[CapturaApoyo]) -> list[dict]:
    if not objs:
        return []
    ids = {x for o in objs for x in (o.nivel_socioeconomico_id, o.grupo_edad_id) if x}
    cat = {c.id: c.nombre for c in ctx.db.scalars(select(CatalogoMunicipio).where(CatalogoMunicipio.id.in_(ids)))} if ids else {}
    bens = {b.id: b for b in ctx.db.scalars(select(Beneficiario).where(Beneficiario.id.in_({o.beneficiario_id for o in objs})))}
    apoyos = {a.id: a.nombre for a in ctx.db.scalars(select(Apoyo).where(Apoyo.id.in_({o.apoyo_id for o in objs})))}
    desc_ids = {o.descripcion_apoyo_id for o in objs if o.descripcion_apoyo_id}
    descs = {d.id: d.nombre for d in ctx.db.scalars(select(DescripcionApoyo).where(DescripcionApoyo.id.in_(desc_ids)))} if desc_ids else {}
    return [{"id": o.id, "beneficiario_id": o.beneficiario_id, "curp": bens[o.beneficiario_id].curp,
             "nombre": bens[o.beneficiario_id].nombre, "programa_id": o.programa_id, "edad": o.edad,
             "grupo_edad": cat.get(o.grupo_edad_id), "nivel_socioeconomico": cat.get(o.nivel_socioeconomico_id),
             "apoyo_id": o.apoyo_id, "apoyo": apoyos.get(o.apoyo_id), "cantidad": o.cantidad,
             "descripcion_apoyo": descs.get(o.descripcion_apoyo_id), "observaciones": o.observaciones,
             "fecha_entrega": o.fecha_entrega.isoformat(), "fecha_registro": o.fecha_registro.isoformat(),
             "es_ejemplo": o.es_ejemplo} for o in objs]


def capturas_del_dia(ctx: Ctx, fecha: date | None = None) -> list[dict]:
    """Capturas registradas en el día (por defecto hoy) en los programas que el usuario puede ver."""
    stmt = select(CapturaApoyo).where(CapturaApoyo.fecha_registro == (fecha or hoy()))
    if ctx.visibles is not None:
        stmt = stmt.where(CapturaApoyo.programa_id.in_(ctx.visibles))
    return _fila_captura(ctx, list(ctx.db.scalars(stmt.order_by(CapturaApoyo.created_at.desc()))))


def contexto(ctx: Ctx) -> dict:
    return {"hoy": hoy().isoformat()}


def crear_captura(ctx: Ctx, datos: dict) -> dict:
    programa_id = datos.get("programa_id")
    p = ctx.db.get(Programa, programa_id) if programa_id else None
    vpd.validar_programa_asignado(p is not None, bool(p and p.activo), ctx.visibles, programa_id)
    b = ctx.db.get(Beneficiario, datos["beneficiario_id"]) if datos.get("beneficiario_id") else None
    if b is None:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Beneficiario inexistente", {"beneficiario_id": "Seleccione un beneficiario"})
    a = ctx.db.get(Apoyo, datos["apoyo_id"]) if datos.get("apoyo_id") else None
    if a is None:
        raise ApiError(422, "JERARQUIA_INVALIDA", "Apoyo inexistente", {"apoyo_id": "Seleccione un apoyo"})
    vpd.validar_apoyo_del_programa(a.programa_id, programa_id)
    desc_id = datos.get("descripcion_apoyo_id")
    if desc_id:
        d = ctx.db.get(DescripcionApoyo, desc_id)
        if d is None:
            raise ApiError(422, "JERARQUIA_INVALIDA", "Descripción inexistente", {"descripcion_apoyo_id": "Descripción inválida"})
        vpd.validar_descripcion_del_apoyo(d.apoyo_id, a.id)
    nivel_id = datos.get("nivel_socioeconomico_id")
    if nivel_id:
        n = ctx.db.get(CatalogoMunicipio, nivel_id)
        if n is None or n.tipo != "nivel_socioeconomico":
            raise ApiError(422, "JERARQUIA_INVALIDA", "Nivel inválido", {"nivel_socioeconomico_id": "Nivel inválido"})
    cantidad = vpd.validar_cantidad(datos.get("cantidad", 1))
    entrega = datos.get("fecha_entrega") or hoy()
    calc = calculo(ctx, b.id, entrega)
    o = CapturaApoyo(municipio_id=ctx.actor.municipio_id, beneficiario_id=b.id, programa_id=programa_id, apoyo_id=a.id,
                     descripcion_apoyo_id=desc_id or None, nivel_socioeconomico_id=nivel_id or None,
                     grupo_edad_id=calc["grupo_edad_id"], edad=calc["edad"], cantidad=cantidad,
                     fecha_entrega=entrega, fecha_registro=hoy(), observaciones=_texto(datos.get("observaciones")),
                     usuario_id=ctx.actor.usuario_id)
    ctx.db.add(o)
    ctx.db.flush()
    ctx.bitacora("captura_apoyo", "crear", o.id, {"beneficiario_id": str(b.id), "apoyo_id": str(a.id)})
    return _fila_captura(ctx, [o])[0]


def eliminar_captura(ctx: Ctx, id_: uuid.UUID) -> None:
    o = ctx.db.get(CapturaApoyo, id_)
    if o is None or (ctx.visibles is not None and o.programa_id not in ctx.visibles):
        raise ApiError(404, "NO_ENCONTRADO", "Captura no encontrada")
    ctx.db.delete(o)
    ctx.db.flush()
    ctx.bitacora("captura_apoyo", "eliminar", id_, {})
