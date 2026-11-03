"""Geografía: carga tolerante de plantillas y copia a municipios existentes (sin duplicar, sin pisar
lo editado, omitiendo huérfanos)."""
import pytest
from sqlalchemy import func, select, update

from app.models import CatalogoMunicipio, GeografiaEstado, GeografiaLocalidad, GeografiaMunicipio, Municipio
from .conftest import crear_municipio
from app.services.geografia import cargar_geografia, copiar_geografia_a_municipio

MUNIS = [
    {"estado_clave": "11", "clave": "003", "nombre": "Apaseo el Alto"},
    {"estado_clave": "11", "clave": "007", "nombre": "Celaya"},
    {"estado_clave": "22", "clave": "001", "nombre": "Amealco"},
]
LOCS = [
    {"estado_clave": "11", "municipio_clave": "003", "clave": "0001", "nombre": "Apaseo el Alto"},
    {"estado_clave": "11", "municipio_clave": "003", "clave": "0002", "nombre": "La Cuevita"},
    {"estado_clave": "11", "municipio_clave": "007", "clave": "0001", "nombre": "Celaya"},
    {"estado_clave": "22", "municipio_clave": "001", "clave": "0001", "nombre": "Amealco"},
]


def _n(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


@pytest.fixture()
def mun(admin, db):
    assert crear_municipio(admin).status_code == 201
    m = db.scalar(select(Municipio).where(Municipio.subdominio == "demo"))
    return m


def _geo_de(db, m):
    return {(c.tipo, c.clave, c.padre_id): c for c in db.scalars(select(CatalogoMunicipio).where(
        CatalogoMunicipio.municipio_id == m.id, CatalogoMunicipio.tipo.in_(["geo_municipio", "geo_localidad"])))}


def test_carga_idempotente(db, seeded):
    r = cargar_geografia(db, MUNIS, LOCS)
    assert (r.municipios_cargados, r.localidades_cargadas) == (3, 4)
    r2 = cargar_geografia(db, MUNIS, LOCS)
    assert (r2.municipios_cargados, r2.localidades_cargadas) == (0, 0)
    assert (r2.municipios_existentes, r2.localidades_existentes) == (3, 4)
    assert _n(db, GeografiaLocalidad) == 4


def test_carga_omite_huerfanos_sin_abortar(db, seeded):
    locs = LOCS + [
        {"estado_clave": "11", "municipio_clave": "999", "clave": "0001", "nombre": "Sin municipio"},
        {"estado_clave": "99", "municipio_clave": "003", "clave": "0001", "nombre": "Sin estado"},
        {"estado_clave": "11", "municipio_clave": "003", "clave": "", "nombre": "Sin clave"},
    ]
    munis = MUNIS + [{"estado_clave": "99", "clave": "001", "nombre": "Estado inexistente"}]
    r = cargar_geografia(db, munis, locs)
    assert (r.municipios_cargados, r.municipios_omitidos) == (3, 1)
    assert (r.localidades_cargadas, r.localidades_omitidas) == (4, 3)
    assert len(r.ejemplos) == 4 and "omitidos" in r.resumen()


def test_carga_un_estado(db, seeded):
    r = cargar_geografia(db, MUNIS, LOCS, solo_estado="11")
    assert (r.municipios_cargados, r.localidades_cargadas, r.otro_estado) == (2, 3, 2)
    assert _n(db, GeografiaMunicipio) == 2
    with pytest.raises(ValueError):
        cargar_geografia(db, [], [], solo_estado="77")


def test_carga_por_lotes_pequenos(db, seeded):
    r = cargar_geografia(db, MUNIS, LOCS, lote=1)
    assert (r.municipios_cargados, r.localidades_cargadas) == (3, 4)


def _estado(db, m, clave):
    e = db.scalar(select(GeografiaEstado).where(GeografiaEstado.clave == clave))
    db.execute(update(Municipio).where(Municipio.id == m.id).values(estado_republica_id=e.id))
    db.commit()
    db.refresh(m)


def test_copia_sin_duplicar(db, mun):
    cargar_geografia(db, MUNIS, LOCS)
    _estado(db, mun, "11")
    r = copiar_geografia_a_municipio(db, mun)
    db.commit()
    assert (r.municipios_agregados, r.localidades_agregadas) == (2, 3)
    r2 = copiar_geografia_a_municipio(db, mun)
    db.commit()
    assert (r2.municipios_agregados, r2.localidades_agregadas) == (0, 0)
    assert (r2.municipios_existentes, r2.localidades_existentes) == (2, 3)
    assert len(_geo_de(db, mun)) == 5


def test_copia_no_pisa_lo_editado(db, mun):
    cargar_geografia(db, MUNIS, LOCS)
    _estado(db, mun, "11")
    copiar_geografia_a_municipio(db, mun)
    db.commit()
    celaya = db.scalar(select(CatalogoMunicipio).where(
        CatalogoMunicipio.municipio_id == mun.id, CatalogoMunicipio.tipo == "geo_municipio",
        CatalogoMunicipio.clave == "007"))
    celaya.nombre = "Celaya (editado)"
    db.commit()
    db.execute(update(GeografiaMunicipio).where(GeografiaMunicipio.clave == "007").values(nombre="Otro"))
    db.commit()
    copiar_geografia_a_municipio(db, mun)
    db.commit()
    db.refresh(celaya)
    assert celaya.nombre == "Celaya (editado)"


def test_copia_agrega_lo_nuevo_de_la_plantilla(db, mun):
    cargar_geografia(db, MUNIS[:1], LOCS[:1])
    _estado(db, mun, "11")
    copiar_geografia_a_municipio(db, mun)
    db.commit()
    cargar_geografia(db, MUNIS, LOCS)
    r = copiar_geografia_a_municipio(db, mun)
    db.commit()
    assert (r.municipios_agregados, r.localidades_agregadas) == (1, 2)


def test_copia_sin_estado(db, mun):
    cargar_geografia(db, MUNIS, LOCS)
    db.execute(update(Municipio).where(Municipio.id == mun.id).values(estado_republica_id=None))
    db.commit()
    db.refresh(mun)
    r = copiar_geografia_a_municipio(db, mun)
    assert r.municipios_agregados == 0 and "sin estado" in r.resumen()
