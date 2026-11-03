"""Geografía INEGI: carga de las plantillas globales (desde CSV, por lotes) y copia a municipios
que ya existen. Ambas operaciones son repetibles: una segunda corrida no agrega nada."""
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..models import (CatalogoMunicipio, GeografiaEstado, GeografiaLocalidad, GeografiaMunicipio,
                      Municipio)

LOTE = 5000
MAX_EJEMPLOS = 20


@dataclass
class ReporteCarga:
    estados: int = 0                      # estados presentes en la plantilla tras la carga
    municipios_cargados: int = 0
    municipios_existentes: int = 0
    municipios_omitidos: int = 0
    localidades_cargadas: int = 0
    localidades_existentes: int = 0
    localidades_omitidas: int = 0
    otro_estado: int = 0                  # filas ignoradas por no ser del estado pedido
    motivos: Counter = field(default_factory=Counter)
    ejemplos: list[str] = field(default_factory=list)

    def omitir(self, tipo: str, motivo: str, fila: dict) -> None:
        if tipo == "municipio":
            self.municipios_omitidos += 1
        else:
            self.localidades_omitidas += 1
        self.motivos[f"{tipo}: {motivo}"] += 1
        if len(self.ejemplos) < MAX_EJEMPLOS:
            self.ejemplos.append(f"{tipo} {motivo}: {dict(fila)}")

    def resumen(self) -> str:
        lineas = [
            f"estados en la plantilla: {self.estados}",
            f"municipios: {self.municipios_cargados} cargados, {self.municipios_existentes} ya existían, "
            f"{self.municipios_omitidos} omitidos",
            f"localidades: {self.localidades_cargadas} cargadas, {self.localidades_existentes} ya existían, "
            f"{self.localidades_omitidas} omitidas",
        ]
        if self.otro_estado:
            lineas.append(f"filas ignoradas por ser de otro estado: {self.otro_estado}")
        for motivo, n in self.motivos.most_common():
            lineas.append(f"  omitidos por {motivo}: {n}")
        if self.ejemplos:
            lineas.append(f"primeros omitidos (máx. {MAX_EJEMPLOS}):")
            lineas += [f"  {e}" for e in self.ejemplos]
        return "\n".join(lineas)


def _limpio(fila: dict, *campos: str) -> list[str] | None:
    """Valores sin espacios de los campos pedidos, o None si falta alguno."""
    valores = [(fila.get(c) or "").strip() for c in campos]
    return valores if all(valores) else None


def _lotes(filas: Iterable[dict], n: int) -> Iterator[list[dict]]:
    lote: list[dict] = []
    for f in filas:
        lote.append(f)
        if len(lote) >= n:
            yield lote
            lote = []
    if lote:
        yield lote


def cargar_geografia(db: Session, municipios: Iterable[dict], localidades: Iterable[dict],
                     solo_estado: str | None = None, lote: int = LOTE) -> ReporteCarga:
    """Carga municipios y localidades INEGI. Tolera datos incompletos: una fila cuyo estado o
    municipio no existe (o con campos vacíos) se omite y se reporta, nunca aborta. Recibe iteradores
    (se leen en streaming, no se materializa el archivo); `solo_estado` (clave INEGI, p. ej. "11")
    ignora las filas de los demás estados. Confirma por lote."""
    rep = ReporteCarga()
    estados = {e.clave: e.id for e in db.scalars(select(GeografiaEstado))}
    if solo_estado is not None and solo_estado not in estados:
        raise ValueError(f"El estado {solo_estado!r} no existe en la plantilla")
    ids_alcance = [estados[solo_estado]] if solo_estado else list(estados.values())
    clave_de_estado = {v: k for k, v in estados.items()}

    munis: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
    for estado_id in ids_alcance:
        for mid, clave in db.execute(select(GeografiaMunicipio.id, GeografiaMunicipio.clave).where(
                GeografiaMunicipio.estado_id == estado_id)):
            munis[(estado_id, clave)] = mid

    def en_alcance(fila: dict) -> bool:
        if solo_estado is not None and (fila.get("estado_clave") or "").strip() != solo_estado:
            rep.otro_estado += 1
            return False
        return True

    for grupo in _lotes(municipios, lote):
        nuevos = []
        for f in grupo:
            if not en_alcance(f):
                continue
            v = _limpio(f, "estado_clave", "clave", "nombre")
            if v is None:
                rep.omitir("municipio", "campos vacíos", f)
                continue
            estado_id = estados.get(v[0])
            if estado_id is None:
                rep.omitir("municipio", f"estado {v[0]} inexistente", f)
                continue
            if (estado_id, v[1]) in munis:
                rep.municipios_existentes += 1
                continue
            mid = uuid.uuid4()
            munis[(estado_id, v[1])] = mid
            nuevos.append({"id": mid, "estado_id": estado_id, "clave": v[1], "nombre": v[2]})
        if nuevos:
            db.execute(insert(GeografiaMunicipio), nuevos)
            rep.municipios_cargados += len(nuevos)
        db.commit()

    claves_loc: set[tuple[uuid.UUID, str]] = set()
    for estado_id in ids_alcance:
        claves_loc.update(tuple(r) for r in db.execute(
            select(GeografiaLocalidad.municipio_geo_id, GeografiaLocalidad.clave)
            .join(GeografiaMunicipio, GeografiaMunicipio.id == GeografiaLocalidad.municipio_geo_id)
            .where(GeografiaMunicipio.estado_id == estado_id)))

    for grupo in _lotes(localidades, lote):
        nuevos = []
        for f in grupo:
            if not en_alcance(f):
                continue
            v = _limpio(f, "estado_clave", "municipio_clave", "clave", "nombre")
            if v is None:
                rep.omitir("localidad", "campos vacíos", f)
                continue
            estado_id = estados.get(v[0])
            if estado_id is None:
                rep.omitir("localidad", f"estado {v[0]} inexistente", f)
                continue
            mid = munis.get((estado_id, v[1]))
            if mid is None:
                rep.omitir("localidad", f"municipio {v[0]}/{v[1]} inexistente", f)
                continue
            if (mid, v[2]) in claves_loc:
                rep.localidades_existentes += 1
                continue
            claves_loc.add((mid, v[2]))
            nuevos.append({"id": uuid.uuid4(), "municipio_geo_id": mid, "clave": v[2], "nombre": v[3]})
        if nuevos:
            db.execute(insert(GeografiaLocalidad), nuevos)
            rep.localidades_cargadas += len(nuevos)
        db.commit()

    rep.estados = len({k[0] for k in munis}) if solo_estado is None else len(
        {clave_de_estado[k[0]] for k in munis})
    return rep


@dataclass
class ReporteCopia:
    subdominio: str
    municipios_agregados: int = 0
    municipios_existentes: int = 0
    municipios_en_conflicto: int = 0      # misma clave ya usada en el municipio con otro estado
    localidades_agregadas: int = 0
    localidades_existentes: int = 0
    nota: str = ""

    def resumen(self) -> str:
        if self.nota:
            return f"{self.subdominio}: {self.nota}"
        return (f"{self.subdominio}: municipios +{self.municipios_agregados} "
                f"({self.municipios_existentes} ya estaban, {self.municipios_en_conflicto} en conflicto); "
                f"localidades +{self.localidades_agregadas} ({self.localidades_existentes} ya estaban)")


def copiar_geografia_a_municipio(db: Session, municipio: Municipio, lote: int = LOTE) -> ReporteCopia:
    """Agrega al municipio los municipios y localidades de la plantilla de SU estado que le falten.
    Nunca modifica ni borra filas existentes (lo que el municipio editó se respeta) y no duplica.
    Efecto secundario aceptado: una fila que el municipio borró se vuelve a agregar."""
    rep = ReporteCopia(municipio.subdominio)
    if municipio.estado_republica_id is None:
        rep.nota = "sin estado de la república asignado; no se copió nada"
        return rep
    mid = municipio.id
    estado_id = str(municipio.estado_republica_id)

    propios: dict[str, CatalogoMunicipio] = {
        c.clave: c for c in db.scalars(select(CatalogoMunicipio).where(
            CatalogoMunicipio.municipio_id == mid, CatalogoMunicipio.tipo == "geo_municipio"))}

    padre_de: dict[uuid.UUID, uuid.UUID] = {}      # id plantilla -> id fila del municipio
    nuevos = []
    for g in db.scalars(select(GeografiaMunicipio).where(
            GeografiaMunicipio.estado_id == municipio.estado_republica_id)):
        fila = propios.get(g.clave)
        if fila is None:
            nid = uuid.uuid4()
            nuevos.append({"id": nid, "municipio_id": mid, "tipo": "geo_municipio", "clave": g.clave,
                           "nombre": g.nombre, "padre_id": None, "datos": {}})
            padre_de[g.id] = nid
        elif (fila.datos or {}).get("estado_id", estado_id) != estado_id:
            rep.municipios_en_conflicto += 1       # la clave la ocupa un municipio de otro estado
        else:
            rep.municipios_existentes += 1
            padre_de[g.id] = fila.id
    if nuevos:
        db.execute(insert(CatalogoMunicipio), nuevos)
        rep.municipios_agregados = len(nuevos)

    existentes = set(tuple(r) for r in db.execute(
        select(CatalogoMunicipio.padre_id, CatalogoMunicipio.clave).where(
            CatalogoMunicipio.municipio_id == mid, CatalogoMunicipio.tipo == "geo_localidad")))
    pendientes = []

    def vaciar() -> None:
        if pendientes:
            db.execute(insert(CatalogoMunicipio), list(pendientes))
            rep.localidades_agregadas += len(pendientes)
            pendientes.clear()

    consulta = select(GeografiaLocalidad).where(
        GeografiaLocalidad.municipio_geo_id.in_(list(padre_de))) if padre_de else None
    for l in (db.scalars(consulta).yield_per(lote) if consulta is not None else ()):
        padre = padre_de[l.municipio_geo_id]
        if (padre, l.clave) in existentes:
            rep.localidades_existentes += 1
            continue
        existentes.add((padre, l.clave))
        pendientes.append({"id": uuid.uuid4(), "municipio_id": mid, "tipo": "geo_localidad",
                           "clave": l.clave, "nombre": l.nombre, "padre_id": padre, "datos": {}})
        if len(pendientes) >= lote:
            vaciar()
    vaciar()
    return rep
