"""Fase 5, parte 1 — catálogos del Padrón: Apoyos, Descripciones de apoyo, Niveles socioeconómicos, Grupos de
edad, Municipios, Localidades y Colonias.

Apoyos, descripciones y colonias son tablas propias (arrancan vacías). Municipios, localidades, grupos de edad
y niveles son las copias de plantilla que el municipio ya tiene en `catalogo_municipio` (Fase 0). Borrado real,
pero solo si nada lo usa (`validar_borrable`); cada alta, cambio y baja queda en bitácora.
"""
import io
import uuid
from collections import defaultdict
from typing import Callable

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import validators_padron as vpd
from ..deps import ActorCtx
from ..errors import ApiError
from ..models import (Apoyo, CatalogoMunicipio, Colonia, DescripcionApoyo, GeografiaEstado, Municipio,
                      Programa)
from . import programas as psvc
from .bitacora import registrar

# Qué más usa un registro (clave: entidad). La parte 2 agrega aquí las entregas, p. ej.:
#   USOS_EXTRA["apoyo"].append(("entregas", lambda db, id: db.scalar(select(func.count()).where(...))))
USOS_EXTRA: dict[str, list[tuple[str, Callable[[Session, uuid.UUID], int]]]] = defaultdict(list)


class Ctx:
    def __init__(self, db: Session, actor: ActorCtx):
        self.db, self.actor = db, actor
        self.tenant = db.get(Municipio, actor.municipio_id)
        self.visibles = psvc.visibles(db, actor.tipo_usuario, actor.usuario_id)  # None = todos los programas

    def bitacora(self, entidad: str, accion: str, id_: uuid.UUID, detalle: dict) -> None:
        registrar(self.db, actor_tipo=self.actor.actor_tipo, actor_id=self.actor.actor_id,
                  accion=f"{entidad}.{accion}", entidad=entidad, entidad_id=id_,
                  municipio_id=self.actor.municipio_id, detalle=detalle)


def _texto(valor) -> str | None:
    valor = (valor or "").strip() if isinstance(valor, str) or valor is None else str(valor).strip()
    return valor or None


def _como(stmt, columna, valor):
    """Filtro de búsqueda por subcadena, sin importar mayúsculas."""
    valor = _texto(valor)
    return stmt.where(func.lower(columna).like(f"%{valor.lower()}%")) if valor else stmt


def _clave_y_nombre(datos: dict, actual=None) -> tuple[str, str]:
    errores = {}
    clave = (datos.get("clave", actual.clave if actual else None) or "").strip()
    nombre = (datos.get("nombre", actual.nombre if actual else None) or "").strip()
    if not clave:
        errores["clave"] = "La clave es obligatoria"
    elif len(clave) > 32:
        errores["clave"] = "Máximo 32 caracteres"
    if not nombre:
        errores["nombre"] = "El nombre es obligatorio"
    if errores:
        raise ApiError(422, "VALIDACION", "Datos inválidos", errores)
    return clave, nombre


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError:  # carrera con otra alta de la misma clave
        db.rollback()
        raise ApiError(409, "CLAVE_DUPLICADA", "Ya existe un registro con esa clave", {"clave": "Ya existe"})


class Cat:
    ruta: str
    entidad: str
    modelo: type
    columnas: list[tuple[str, str]]  # (encabezado, llave de la fila) en pantalla y en el Excel

    def _base(self, ctx: Ctx):
        return select(self.modelo)

    def _visible(self, ctx: Ctx, o) -> bool:
        return True

    def obtener(self, ctx: Ctx, id_: uuid.UUID):
        o = ctx.db.get(self.modelo, id_)  # la Session ya filtra por municipio
        if o is None or not self._visible(ctx, o):
            raise ApiError(404, "NO_ENCONTRADO", "Registro no encontrado")
        return o

    def listar(self, ctx: Ctx, f: dict) -> list[dict]:
        raise NotImplementedError

    def usos(self, ctx: Ctx, o) -> dict[str, int]:
        return {}

    def crear(self, ctx: Ctx, datos: dict):
        raise NotImplementedError

    def editar(self, ctx: Ctx, id_: uuid.UUID, datos: dict):
        raise NotImplementedError

    def fila(self, ctx: Ctx, o) -> dict:
        return self.listar_filas(ctx, [o])[0]

    def listar_filas(self, ctx: Ctx, objs: list) -> list[dict]:
        raise NotImplementedError

    def eliminar(self, ctx: Ctx, id_: uuid.UUID) -> None:
        o = self.obtener(ctx, id_)
        usos = dict(self.usos(ctx, o))
        for etiqueta, contar in USOS_EXTRA[self.entidad]:
            usos[etiqueta] = contar(ctx.db, o.id)
        vpd.validar_borrable(usos)
        clave = o.clave
        ctx.db.delete(o)
        ctx.db.flush()
        ctx.bitacora(self.entidad, "eliminar", id_, {"clave": clave})

    def eliminar_lote(self, ctx: Ctx, ids: list[uuid.UUID]) -> dict:
        """Elimina lo que se puede y reporta lo demás (un registro en uso no frena al resto)."""
        eliminados, rechazados = 0, []
        for id_ in vpd.ids_unicos(ids):
            try:  # `eliminar` valida antes de tocar la base: un rechazo no deja nada a medias
                self.eliminar(ctx, id_)
                eliminados += 1
            except ApiError as e:
                rechazados.append({"id": id_, "codigo": e.codigo, "motivo": e.mensaje})
        return {"eliminados": eliminados, "rechazados": rechazados}

    def exportar(self, ctx: Ctx, f: dict) -> bytes:
        filas = self.listar(ctx, f)
        wb = Workbook()
        ws = wb.active
        ws.title = self.entidad[:31]
        ws.append([h for h, _ in self.columnas])
        for c in ws[1]:
            c.font = Font(bold=True)
        for fila in filas:
            ws.append([fila.get(k) if fila.get(k) is not None else "" for _, k in self.columnas])
        for i, (h, k) in enumerate(self.columnas, start=1):
            ancho = max([len(h)] + [len(str(fila.get(k) or "")) for fila in filas]) + 2
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(ancho, 60)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()


# --------------------------------------------------------------------------- tablas propias
def _programas_nombre(ctx: Ctx) -> dict[uuid.UUID, str]:
    return {p.id: f"{p.clave} — {p.nombre}" for p in ctx.db.scalars(select(Programa))}


class Apoyos(Cat):
    ruta, entidad, modelo = "apoyos", "apoyo", Apoyo
    columnas = [("Clave", "clave"), ("Apoyo", "nombre"), ("Observaciones", "observaciones")]

    def _base(self, ctx):
        stmt = select(Apoyo)
        return stmt if ctx.visibles is None else stmt.where(Apoyo.programa_id.in_(ctx.visibles))

    def _visible(self, ctx, o):
        return ctx.visibles is None or o.programa_id in ctx.visibles

    def listar_filas(self, ctx, objs):
        progs = _programas_nombre(ctx)
        return [{"id": o.id, "clave": o.clave, "nombre": o.nombre, "programa_id": o.programa_id,
                 "programa": progs.get(o.programa_id), "observaciones": o.observaciones} for o in objs]

    def listar(self, ctx, f):
        stmt = _como(_como(self._base(ctx), Apoyo.clave, f.get("clave")), Apoyo.nombre, f.get("nombre"))
        if f.get("programa_id"):
            stmt = stmt.where(Apoyo.programa_id == f["programa_id"])
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(Apoyo.clave))))

    def usos(self, ctx, o):
        return {"descripciones de apoyo": ctx.db.scalar(
            select(func.count()).select_from(DescripcionApoyo).where(DescripcionApoyo.apoyo_id == o.id))}

    def _programa(self, ctx, programa_id):
        p = ctx.db.get(Programa, programa_id) if programa_id else None
        vpd.validar_programa_asignado(p is not None, bool(p and p.activo), ctx.visibles, programa_id)

    def _clave_libre(self, ctx, clave, excepto=None):
        stmt = select(Apoyo.clave)
        if excepto:
            stmt = stmt.where(Apoyo.id != excepto)
        vpd.levantar_si_clave_repetida(clave, ctx.db.scalars(stmt))

    def crear(self, ctx, datos):
        clave, nombre = _clave_y_nombre(datos)
        self._programa(ctx, datos.get("programa_id"))
        self._clave_libre(ctx, clave)
        o = Apoyo(municipio_id=ctx.actor.municipio_id, clave=clave, nombre=nombre,
                  programa_id=datos["programa_id"], observaciones=_texto(datos.get("observaciones")))
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave, "programa_id": str(o.programa_id)})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        clave, nombre = _clave_y_nombre(datos, o)
        if datos.get("programa_id") not in (None, o.programa_id):
            self._programa(ctx, datos["programa_id"])
            o.programa_id = datos["programa_id"]
        self._clave_libre(ctx, clave, o.id)
        o.clave, o.nombre = clave, nombre
        if "observaciones" in datos:
            o.observaciones = _texto(datos["observaciones"])
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": clave})
        return o


class Descripciones(Cat):
    ruta, entidad, modelo = "descripciones-apoyo", "descripcion_apoyo", DescripcionApoyo
    columnas = [("Clave", "clave"), ("Descripción de Apoyo", "nombre"), ("Observaciones", "observaciones")]

    def _base(self, ctx):
        stmt = select(DescripcionApoyo)
        if ctx.visibles is None:
            return stmt
        return stmt.where(DescripcionApoyo.apoyo_id.in_(select(Apoyo.id).where(Apoyo.programa_id.in_(ctx.visibles))))

    def _visible(self, ctx, o):
        return ctx.visibles is None or self._apoyo_visible(ctx, o.apoyo_id)

    def _apoyo_visible(self, ctx, apoyo_id) -> bool:
        a = ctx.db.get(Apoyo, apoyo_id) if apoyo_id else None
        return a is not None and (ctx.visibles is None or a.programa_id in ctx.visibles)

    def listar_filas(self, ctx, objs):
        apoyos = {a.id: f"{a.clave} — {a.nombre}" for a in ctx.db.scalars(select(Apoyo))}
        return [{"id": o.id, "clave": o.clave, "nombre": o.nombre, "apoyo_id": o.apoyo_id,
                 "apoyo": apoyos.get(o.apoyo_id), "observaciones": o.observaciones} for o in objs]

    def listar(self, ctx, f):
        stmt = _como(_como(self._base(ctx), DescripcionApoyo.clave, f.get("clave")), DescripcionApoyo.nombre, f.get("nombre"))
        if f.get("apoyo_id"):
            stmt = stmt.where(DescripcionApoyo.apoyo_id == f["apoyo_id"])
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(DescripcionApoyo.clave))))

    def _apoyo(self, ctx, apoyo_id):
        existe = bool(apoyo_id) and ctx.db.get(Apoyo, apoyo_id) is not None
        vpd.validar_apoyo_existente(existe, existe and self._apoyo_visible(ctx, apoyo_id), apoyo_id)

    def _clave_libre(self, ctx, clave, excepto=None):
        stmt = select(DescripcionApoyo.clave)
        if excepto:
            stmt = stmt.where(DescripcionApoyo.id != excepto)
        vpd.levantar_si_clave_repetida(clave, ctx.db.scalars(stmt))

    def crear(self, ctx, datos):
        clave, nombre = _clave_y_nombre(datos)
        self._apoyo(ctx, datos.get("apoyo_id"))
        self._clave_libre(ctx, clave)
        o = DescripcionApoyo(municipio_id=ctx.actor.municipio_id, clave=clave, nombre=nombre,
                             apoyo_id=datos["apoyo_id"], observaciones=_texto(datos.get("observaciones")))
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave, "apoyo_id": str(o.apoyo_id)})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        clave, nombre = _clave_y_nombre(datos, o)
        if datos.get("apoyo_id") not in (None, o.apoyo_id):
            self._apoyo(ctx, datos["apoyo_id"])
            o.apoyo_id = datos["apoyo_id"]
        self._clave_libre(ctx, clave, o.id)
        o.clave, o.nombre = clave, nombre
        if "observaciones" in datos:
            o.observaciones = _texto(datos["observaciones"])
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": clave})
        return o


# --------------------------------------------------------------------------- copias de plantilla (catalogo_municipio)
def _estados(ctx: Ctx) -> dict[uuid.UUID, str]:
    return {e.id: e.nombre for e in ctx.db.scalars(select(GeografiaEstado))}


def estado_de_municipio(ctx: Ctx, o: CatalogoMunicipio) -> uuid.UUID | None:
    """El estado del municipio: el que se guardó al darlo de alta o, en las copias de plantilla, el estado del
    municipio de la plataforma (solo se copian los municipios de ese estado)."""
    guardado = (o.datos or {}).get("estado_id")
    return uuid.UUID(guardado) if guardado else ctx.tenant.estado_republica_id


class Generico(Cat):
    tipo: str
    modelo = CatalogoMunicipio

    def _base(self, ctx):
        return select(CatalogoMunicipio).where(CatalogoMunicipio.tipo == self.tipo)

    def obtener(self, ctx, id_):
        o = ctx.db.get(CatalogoMunicipio, id_)
        if o is None or o.tipo != self.tipo:
            raise ApiError(404, "NO_ENCONTRADO", "Registro no encontrado")
        return o

    def _claves(self, ctx, excepto=None, padre_id=None):
        stmt = select(CatalogoMunicipio.clave).where(CatalogoMunicipio.tipo == self.tipo)
        if padre_id:
            stmt = stmt.where(CatalogoMunicipio.padre_id == padre_id)
        if excepto:
            stmt = stmt.where(CatalogoMunicipio.id != excepto)
        return ctx.db.scalars(stmt)

    def listar(self, ctx, f):
        stmt = _como(_como(self._base(ctx), CatalogoMunicipio.clave, f.get("clave")), CatalogoMunicipio.nombre, f.get("nombre"))
        stmt = self._filtrar(stmt, f)
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(CatalogoMunicipio.clave, CatalogoMunicipio.nombre))))

    def _filtrar(self, stmt, f):
        return stmt



class Municipios(Generico):
    ruta, entidad, tipo = "geo/municipios", "geo_municipio", "geo_municipio"
    columnas = [("Clave", "clave"), ("Municipio", "nombre"), ("Estado", "estado")]

    def listar_filas(self, ctx, objs):
        estados = _estados(ctx)
        return [{"id": o.id, "clave": o.clave, "nombre": o.nombre,
                 "estado_id": (e := estado_de_municipio(ctx, o)), "estado": estados.get(e)} for o in objs]

    def _filtrar(self, stmt, f):
        return stmt

    def listar(self, ctx, f):
        filas = super().listar(ctx, f)
        return [x for x in filas if not f.get("estado_id") or x["estado_id"] == f["estado_id"]]

    def usos(self, ctx, o):
        n = lambda m: ctx.db.scalar(select(func.count()).select_from(m).where(
            (m.padre_id if m is CatalogoMunicipio else m.municipio_geo_id) == o.id))
        return {"localidades": n(CatalogoMunicipio), "colonias": n(Colonia)}

    def _estado(self, ctx, datos, actual=None) -> uuid.UUID:
        estado_id = datos.get("estado_id") or (estado_de_municipio(ctx, actual) if actual else ctx.tenant.estado_republica_id)
        if estado_id is None or ctx.db.get(GeografiaEstado, estado_id) is None:
            raise ApiError(422, "JERARQUIA_INVALIDA", "Estado inválido", {"estado_id": "Estado inválido"})
        return estado_id

    def crear(self, ctx, datos):
        clave, nombre = _clave_y_nombre(datos)
        estado_id = self._estado(ctx, datos)
        vpd.levantar_si_clave_repetida(clave, self._claves(ctx))
        o = CatalogoMunicipio(id=uuid.uuid4(), municipio_id=ctx.actor.municipio_id, tipo=self.tipo, clave=clave,
                              nombre=nombre, datos={"estado_id": str(estado_id)})
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        clave, nombre = _clave_y_nombre(datos, o)
        estado_id = self._estado(ctx, datos, o)
        if estado_id != estado_de_municipio(ctx, o) and ctx.db.scalar(
                select(func.count()).select_from(Colonia).where(Colonia.municipio_geo_id == o.id)):
            raise ApiError(422, "REGISTRO_EN_USO", "El municipio tiene colonias: no se puede cambiar su estado",
                           {"estado_id": "Tiene colonias"})
        vpd.levantar_si_clave_repetida(clave, self._claves(ctx, o.id))
        o.clave, o.nombre, o.datos = clave, nombre, {**(o.datos or {}), "estado_id": str(estado_id)}
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": clave})
        return o


class Localidades(Generico):
    ruta, entidad, tipo = "geo/localidades", "geo_localidad", "geo_localidad"
    columnas = [("Clave", "clave"), ("Localidad", "nombre"), ("Municipio", "municipio"), ("Estado", "estado")]

    def listar_filas(self, ctx, objs):
        estados = _estados(ctx)
        munis = {m.id: m for m in ctx.db.scalars(select(CatalogoMunicipio).where(CatalogoMunicipio.tipo == "geo_municipio"))}
        filas = []
        for o in objs:
            m = munis.get(o.padre_id)
            e = estado_de_municipio(ctx, m) if m else None
            filas.append({"id": o.id, "clave": o.clave, "nombre": o.nombre, "municipio_id": o.padre_id,
                          "municipio": m.nombre if m else None, "estado_id": e, "estado": estados.get(e)})
        return filas

    def listar(self, ctx, f):
        stmt = _como(_como(self._base(ctx), CatalogoMunicipio.clave, f.get("clave")), CatalogoMunicipio.nombre, f.get("nombre"))
        if f.get("municipio_id"):
            stmt = stmt.where(CatalogoMunicipio.padre_id == f["municipio_id"])
        filas = self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(CatalogoMunicipio.clave, CatalogoMunicipio.nombre))))
        return [x for x in filas if not f.get("estado_id") or x["estado_id"] == f["estado_id"]]

    def _municipio(self, ctx, municipio_id) -> CatalogoMunicipio:
        m = ctx.db.get(CatalogoMunicipio, municipio_id) if municipio_id else None
        if m is None or m.tipo != "geo_municipio":
            raise ApiError(422, "JERARQUIA_INVALIDA", "Municipio inexistente", {"municipio_id": "Municipio inválido"})
        return m

    def crear(self, ctx, datos):
        clave, nombre = _clave_y_nombre(datos)
        m = self._municipio(ctx, datos.get("municipio_id"))
        vpd.levantar_si_clave_repetida(clave, self._claves(ctx, padre_id=m.id))  # única por municipio
        o = CatalogoMunicipio(id=uuid.uuid4(), municipio_id=ctx.actor.municipio_id, tipo=self.tipo, clave=clave,
                              nombre=nombre, padre_id=m.id, datos={})
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave, "municipio_id": str(m.id)})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        clave, nombre = _clave_y_nombre(datos, o)
        padre_id = o.padre_id
        if datos.get("municipio_id") not in (None, o.padre_id):
            padre_id = self._municipio(ctx, datos["municipio_id"]).id
        vpd.levantar_si_clave_repetida(clave, self._claves(ctx, o.id, padre_id))
        o.clave, o.nombre, o.padre_id = clave, nombre, padre_id
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": clave})
        return o


class Niveles(Generico):
    ruta, entidad, tipo = "niveles-socioeconomicos", "nivel_socioeconomico", "nivel_socioeconomico"
    columnas = [("Nivel", "nombre")]

    def listar_filas(self, ctx, objs):
        return [{"id": o.id, "clave": o.clave, "nombre": o.nombre} for o in objs]

    def listar(self, ctx, f):
        stmt = _como(self._base(ctx), CatalogoMunicipio.nombre, f.get("nombre"))
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(CatalogoMunicipio.nombre))))

    def _nombre_libre(self, ctx, nombre, excepto=None):
        stmt = select(CatalogoMunicipio.nombre).where(CatalogoMunicipio.tipo == self.tipo)
        if excepto:
            stmt = stmt.where(CatalogoMunicipio.id != excepto)
        vpd.levantar_si_clave_repetida(nombre, ctx.db.scalars(stmt), "nombre")

    def crear(self, ctx, datos):
        nombre = vpd.validar_nombre(datos.get("nombre"))
        clave = vpd.clave_desde_nombre(nombre)  # no se captura: sale del nombre (como en la plantilla)
        if not clave:
            raise ApiError(422, "VALIDACION", "Datos inválidos", {"nombre": "Nombre inválido"})
        self._nombre_libre(ctx, nombre)
        vpd.levantar_si_clave_repetida(clave, self._claves(ctx), "nombre")
        o = CatalogoMunicipio(id=uuid.uuid4(), municipio_id=ctx.actor.municipio_id, tipo=self.tipo, clave=clave,
                              nombre=nombre, datos={})
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        nombre = vpd.validar_nombre(datos.get("nombre", o.nombre))
        self._nombre_libre(ctx, nombre, o.id)
        o.nombre = nombre  # la clave se conserva: otras tablas la referencian
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": o.clave})
        return o


class Grupos(Generico):
    ruta, entidad, tipo = "grupos-edad", "grupo_edad", "grupo_edad"
    columnas = [("Edad", "nombre"), ("Rango min-max", "rango")]

    def listar_filas(self, ctx, objs):
        filas = []
        for o in objs:
            mn, mx = (o.datos or {}).get("edad_min"), (o.datos or {}).get("edad_max")
            filas.append({"id": o.id, "clave": o.clave, "nombre": o.nombre, "edad_min": mn, "edad_max": mx,
                          "rango": vpd.clave_de_rango(mn, mx) if mn is not None else ""})
        return sorted(filas, key=lambda x: (x["edad_min"] is None, x["edad_min"] or 0))

    def listar(self, ctx, f):
        stmt = _como(self._base(ctx), CatalogoMunicipio.nombre, f.get("nombre"))
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt)))

    def _rangos(self, ctx) -> list[vpd.Rango]:
        return [(o.id, (o.datos or {})["edad_min"], (o.datos or {}).get("edad_max"))
                for o in ctx.db.scalars(self._base(ctx)) if (o.datos or {}).get("edad_min") is not None]

    def _nombre_libre(self, ctx, nombre, excepto=None):
        stmt = select(CatalogoMunicipio.nombre).where(CatalogoMunicipio.tipo == self.tipo)
        if excepto:
            stmt = stmt.where(CatalogoMunicipio.id != excepto)
        vpd.levantar_si_clave_repetida(nombre, ctx.db.scalars(stmt), "nombre")

    def crear(self, ctx, datos):
        nombre = vpd.validar_nombre(datos.get("nombre"))
        mn, mx = vpd.validar_rango_edad(datos.get("edad_min"), datos.get("edad_max"))
        vpd.validar_sin_traslape((mn, mx), self._rangos(ctx))
        self._nombre_libre(ctx, nombre)
        clave = vpd.clave_de_rango(mn, mx)
        vpd.levantar_si_clave_repetida(clave, self._claves(ctx), "edad_min")
        o = CatalogoMunicipio(id=uuid.uuid4(), municipio_id=ctx.actor.municipio_id, tipo=self.tipo, clave=clave,
                              nombre=nombre, datos={"edad_min": mn, "edad_max": mx})
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        nombre = vpd.validar_nombre(datos.get("nombre", o.nombre))
        actual = o.datos or {}
        mn, mx = vpd.validar_rango_edad(datos.get("edad_min", actual.get("edad_min")),
                                         datos["edad_max"] if "edad_max" in datos else actual.get("edad_max"))
        vpd.validar_sin_traslape((mn, mx), self._rangos(ctx), excepto=o.id)
        self._nombre_libre(ctx, nombre, o.id)
        o.nombre, o.datos = nombre, {**actual, "edad_min": mn, "edad_max": mx}  # la clave se conserva
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": o.clave})
        return o


class Colonias(Cat):
    ruta, entidad, modelo = "geo/colonias", "colonia", Colonia
    columnas = [("Clave", "clave"), ("Colonia", "nombre"), ("Estado", "estado"), ("Municipio", "municipio")]

    def listar_filas(self, ctx, objs):
        estados = _estados(ctx)
        munis = {m.id: m.nombre for m in ctx.db.scalars(select(CatalogoMunicipio).where(CatalogoMunicipio.tipo == "geo_municipio"))}
        return [{"id": o.id, "clave": o.clave, "nombre": o.nombre, "estado_id": o.estado_id,
                 "estado": estados.get(o.estado_id), "municipio_id": o.municipio_geo_id,
                 "municipio": munis.get(o.municipio_geo_id)} for o in objs]

    def listar(self, ctx, f):
        stmt = _como(_como(select(Colonia), Colonia.clave, f.get("clave")), Colonia.nombre, f.get("nombre"))
        if f.get("estado_id"):
            stmt = stmt.where(Colonia.estado_id == f["estado_id"])
        if f.get("municipio_id"):
            stmt = stmt.where(Colonia.municipio_geo_id == f["municipio_id"])
        return self.listar_filas(ctx, list(ctx.db.scalars(stmt.order_by(Colonia.clave))))

    def _pertenencia(self, ctx, estado_id, municipio_id) -> None:
        m = ctx.db.get(CatalogoMunicipio, municipio_id) if municipio_id else None
        existe = m is not None and m.tipo == "geo_municipio"
        if estado_id is None or ctx.db.get(GeografiaEstado, estado_id) is None:
            raise ApiError(422, "JERARQUIA_INVALIDA", "Estado inválido", {"estado_id": "Estado inválido"})
        vpd.validar_municipio_de_estado(estado_de_municipio(ctx, m) if existe else None, estado_id, existe)

    def _clave_libre(self, ctx, clave, excepto=None):
        stmt = select(Colonia.clave)
        if excepto:
            stmt = stmt.where(Colonia.id != excepto)
        vpd.levantar_si_clave_repetida(clave, ctx.db.scalars(stmt))

    def crear(self, ctx, datos):
        clave, nombre = _clave_y_nombre(datos)
        self._pertenencia(ctx, datos.get("estado_id"), datos.get("municipio_id"))
        self._clave_libre(ctx, clave)
        o = Colonia(municipio_id=ctx.actor.municipio_id, clave=clave, nombre=nombre, estado_id=datos["estado_id"],
                    municipio_geo_id=datos["municipio_id"])
        ctx.db.add(o)
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "crear", o.id, {"clave": clave})
        return o

    def editar(self, ctx, id_, datos):
        o = self.obtener(ctx, id_)
        clave, nombre = _clave_y_nombre(datos, o)
        estado_id = datos.get("estado_id", o.estado_id)
        municipio_id = datos.get("municipio_id", o.municipio_geo_id)
        if (estado_id, municipio_id) != (o.estado_id, o.municipio_geo_id):
            self._pertenencia(ctx, estado_id, municipio_id)
        self._clave_libre(ctx, clave, o.id)
        o.clave, o.nombre, o.estado_id, o.municipio_geo_id = clave, nombre, estado_id, municipio_id
        _flush(ctx.db)
        ctx.bitacora(self.entidad, "editar", o.id, {"clave": clave})
        return o


CATALOGOS: dict[str, Cat] = {c.ruta: c for c in (
    Apoyos(), Descripciones(), Niveles(), Grupos(), Municipios(), Localidades(), Colonias())}


def programas_disponibles(ctx: Ctx) -> list[dict]:
    """Solo los programas activos que el usuario tiene asignados (el administrador, todos): selector de Apoyos."""
    stmt = select(Programa).where(Programa.activo.is_(True))
    if ctx.visibles is not None:
        stmt = stmt.where(Programa.id.in_(ctx.visibles))
    return [{"id": p.id, "ejercicio_fiscal": p.ejercicio_fiscal, "clave": p.clave, "nombre": p.nombre}
            for p in ctx.db.scalars(stmt.order_by(Programa.ejercicio_fiscal.desc(), Programa.clave))]


def estados(ctx: Ctx) -> list[dict]:
    return [{"id": e.id, "clave": e.clave, "nombre": e.nombre}
            for e in ctx.db.scalars(select(GeografiaEstado).order_by(GeografiaEstado.clave))]
