"""Registro de plantillas globales y su copia al espacio de un municipio."""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import (CatalogoMunicipio, ClasificacionProgramatica, Frecuencia, GeografiaEstado, GeografiaLocalidad, GeografiaMunicipio,
                      Municipio, PlantillaAlgoritmo, PlantillaClasificacionProgramatica,
                      PlantillaConac, PlantillaDimension, PlantillaFrecuencia,
                      PlantillaGrupoEdad, PlantillaNivelSocioeconomico)


@dataclass
class Catalogo:
    modelo: type
    extra: tuple[str, ...] = ()  # columnas editables además de clave y nombre


# tipo (URL) -> {nivel: Catalogo}; el nivel "_" es el único nivel de un catálogo plano
REGISTRO: dict[str, dict[str, Catalogo]] = {
    "conac": {"_": Catalogo(PlantillaConac, ("nivel", "padre_id"))},
    "geografia": {
        "estado": Catalogo(GeografiaEstado),
        "municipio": Catalogo(GeografiaMunicipio, ("estado_id",)),
        "localidad": Catalogo(GeografiaLocalidad, ("municipio_geo_id",)),
    },
    "frecuencia": {"_": Catalogo(PlantillaFrecuencia)},
    "dimension": {"_": Catalogo(PlantillaDimension)},
    "algoritmo": {"_": Catalogo(PlantillaAlgoritmo)},
    "grupo_edad": {"_": Catalogo(PlantillaGrupoEdad, ("edad_min", "edad_max"))},
    "nivel_socioeconomico": {"_": Catalogo(PlantillaNivelSocioeconomico)},
    "clasificacion_programatica": {"_": Catalogo(PlantillaClasificacionProgramatica)},
}


def resolver(tipo: str, nivel: str | None) -> Catalogo:
    niveles = REGISTRO.get(tipo)
    if niveles is None:
        raise ApiError(404, "PLANTILLA_NO_ENCONTRADA", f"Plantilla desconocida: {tipo}")
    if "_" in niveles:
        return niveles["_"]
    cat = niveles.get(nivel or "estado")
    if cat is None:
        raise ApiError(422, "NIVEL_INVALIDO", "nivel debe ser estado, municipio o localidad",
                       {"nivel": "Inválido"})
    return cat


def en_uso(db: Session, tipo: str, nivel: str | None, item) -> bool:
    """¿Algo referencia aún este registro? (regla del DELETE de plantillas)"""
    def cuenta(col, valor):
        return db.scalar(select(func.count()).select_from(col.class_).where(col == valor)) > 0

    if tipo == "conac":
        return cuenta(PlantillaConac.padre_id, item.id)
    if tipo == "geografia":
        n = nivel or "estado"
        if n == "estado":
            return cuenta(GeografiaMunicipio.estado_id, item.id) or cuenta(
                Municipio.estado_republica_id, item.id)
        if n == "municipio":
            return cuenta(GeografiaLocalidad.municipio_geo_id, item.id)
    return False


# ------------------------------------------------------------------------ copia a un municipio
_PLANOS = [
    ("dimension", PlantillaDimension, {}),
    ("algoritmo", PlantillaAlgoritmo, {}),
    ("grupo_edad", PlantillaGrupoEdad, {"edad_min", "edad_max"}),
    ("nivel_socioeconomico", PlantillaNivelSocioeconomico, {}),
]


def copiar_plantillas(db: Session, municipio: Municipio) -> dict[str, int]:
    """COPIA (no referencia) las plantillas al espacio del municipio. Geografía solo del
    estado elegido (copiar las ~300 mil localidades de todo el país por municipio no tiene
    sentido). Corre dentro de la transacción de alta."""
    mid = municipio.id
    conteo: dict[str, int] = {}

    # Fase 1: frecuencia y clasificación programática son tablas propias (no filas genéricas)
    for tipo, plantilla, destino in (("frecuencia", PlantillaFrecuencia, Frecuencia),
                                     ("clasificacion_programatica",
                                      PlantillaClasificacionProgramatica,
                                      ClasificacionProgramatica)):
        filas = db.scalars(select(plantilla).order_by(plantilla.clave)).all()
        for f in filas:
            db.add(destino(municipio_id=mid, clave=f.clave, nombre=f.nombre, activo=True))
        conteo[tipo] = len(filas)

    for tipo, modelo, extras in _PLANOS:
        filas = db.scalars(select(modelo).order_by(modelo.clave)).all()
        for f in filas:
            datos = {k: getattr(f, k) for k in extras}
            db.add(CatalogoMunicipio(municipio_id=mid, tipo=tipo, clave=f.clave,
                                     nombre=f.nombre, datos=datos))
        conteo[tipo] = len(filas)

    # CONAC: respeta la jerarquía capítulo > partida > partida específica > artículo
    nuevos: dict[uuid.UUID, CatalogoMunicipio] = {}
    orden = {"capitulo": 0, "partida": 1, "partida_especifica": 2, "articulo": 3}
    conac = sorted(db.scalars(select(PlantillaConac)).all(), key=lambda c: (orden[c.nivel], c.clave))
    for c in conac:
        nuevo = CatalogoMunicipio(
            municipio_id=mid, tipo=f"conac_{c.nivel}", clave=c.clave, nombre=c.nombre,
            padre_id=nuevos[c.padre_id].id if c.padre_id else None)
        nuevo.id = uuid.uuid4()
        db.add(nuevo)
        nuevos[c.id] = nuevo
    conteo["conac"] = len(conac)

    if municipio.estado_republica_id:
        munis = db.scalars(select(GeografiaMunicipio).where(
            GeografiaMunicipio.estado_id == municipio.estado_republica_id)).all()
        mapa: dict[uuid.UUID, CatalogoMunicipio] = {}
        for g in munis:
            n = CatalogoMunicipio(id=uuid.uuid4(), municipio_id=mid, tipo="geo_municipio",
                                  clave=g.clave, nombre=g.nombre)
            db.add(n)
            mapa[g.id] = n
        locs = 0
        if mapa:
            for l in db.scalars(select(GeografiaLocalidad).where(
                    GeografiaLocalidad.municipio_geo_id.in_(list(mapa)))):
                db.add(CatalogoMunicipio(municipio_id=mid, tipo="geo_localidad", clave=l.clave,
                                         nombre=l.nombre, padre_id=mapa[l.municipio_geo_id].id))
                locs += 1
        conteo["geo_municipio"] = len(munis)
        conteo["geo_localidad"] = locs
    return conteo
