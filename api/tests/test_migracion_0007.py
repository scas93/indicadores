"""Migración 0007 (catálogos del Padrón): completa en los municipios ya creados las copias de plantilla que
falten, sin tocar lo existente. El DDL completo se verifica en CI con `alembic upgrade head` sobre Postgres."""
import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (Base, CatalogoMunicipio, GeografiaEstado, GeografiaLocalidad, GeografiaMunicipio, Municipio,
                        PlantillaGrupoEdad, PlantillaNivelSocioeconomico)

RUTA = Path(__file__).parents[1] / "alembic/versions/0007_catalogos_padron.py"
spec = importlib.util.spec_from_file_location("mig0007", RUTA)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def _entorno():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with Session(e) as db:
        est = GeografiaEstado(clave="11", nombre="Guanajuato")
        otro = GeografiaEstado(clave="12", nombre="Otro")
        db.add_all([est, otro])
        db.flush()
        m1 = GeografiaMunicipio(estado_id=est.id, clave="015", nombre="Guanajuato")
        m2 = GeografiaMunicipio(estado_id=otro.id, clave="001", nombre="Ajeno")
        db.add_all([m1, m2, PlantillaGrupoEdad(clave="0-11", nombre="Niñez", edad_min=0, edad_max=11),
                    PlantillaGrupoEdad(clave="60+", nombre="Mayores", edad_min=60, edad_max=None),
                    PlantillaNivelSocioeconomico(clave="bajo", nombre="Bajo")])
        db.flush()
        db.add_all([GeografiaLocalidad(municipio_geo_id=m1.id, clave="0001", nombre="Centro"),
                    GeografiaLocalidad(municipio_geo_id=m2.id, clave="0001", nombre="Ajena")])
        con_estado = Municipio(id=uuid.uuid4(), nombre="Con estado", subdominio="a", estado_republica_id=est.id)
        sin_estado = Municipio(id=uuid.uuid4(), nombre="Sin estado", subdominio="b")
        db.add_all([con_estado, sin_estado])
        db.commit()
        return e, con_estado.id, sin_estado.id


def _conteo(e, mid):
    with Session(e) as db:
        filas = db.scalars(select(CatalogoMunicipio).where(CatalogoMunicipio.municipio_id == mid)).all()
        out = {}
        for f in filas:
            out.setdefault(f.tipo, []).append(f)
        return out


def test_completa_lo_que_falta_y_solo_de_su_estado():
    e, con, sin = _entorno()
    with e.begin() as c:
        agregadas = mig._completar_copias(c)
    assert agregadas == {"grupo_edad": 4, "nivel_socioeconomico": 2, "geo_municipio": 1, "geo_localidad": 1}
    a, b = _conteo(e, con), _conteo(e, sin)
    assert {t: len(v) for t, v in a.items()} == {"grupo_edad": 2, "nivel_socioeconomico": 1, "geo_municipio": 1, "geo_localidad": 1}
    assert {t: len(v) for t, v in b.items()} == {"grupo_edad": 2, "nivel_socioeconomico": 1}  # sin estado: sin geografía
    assert [g.nombre for g in a["geo_municipio"]] == ["Guanajuato"]  # no se cuela el municipio de otro estado
    assert a["geo_localidad"][0].padre_id == a["geo_municipio"][0].id
    abierto = next(g for g in a["grupo_edad"] if g.clave == "60+")
    assert abierto.datos == {"edad_min": 60, "edad_max": None}


def test_es_idempotente_y_no_toca_lo_existente():
    e, con, _ = _entorno()
    with e.begin() as c:
        mig._completar_copias(c)
    with Session(e) as db:  # el municipio renombró un grupo: la migración no lo pisa
        g = db.scalar(select(CatalogoMunicipio).where(CatalogoMunicipio.municipio_id == con, CatalogoMunicipio.clave == "0-11"))
        g.nombre = "Infancia"
        db.commit()
    with e.begin() as c:
        assert mig._completar_copias(c) == {"grupo_edad": 0, "nivel_socioeconomico": 0, "geo_municipio": 0, "geo_localidad": 0}
    assert next(g for g in _conteo(e, con)["grupo_edad"] if g.clave == "0-11").nombre == "Infancia"


def test_el_indice_parcial_impide_claves_planas_repetidas_en_el_mismo_municipio():
    e, con, sin = _entorno()
    with e.begin() as c:
        mig._completar_copias(c)
    with Session(e) as db:
        db.add(CatalogoMunicipio(municipio_id=con, tipo="grupo_edad", clave="0-11", nombre="Repetido", datos={}))
        try:
            db.commit()
            assert False, "debió fallar"
        except sa.exc.IntegrityError:
            db.rollback()
        db.add(CatalogoMunicipio(municipio_id=sin, tipo="grupo_edad", clave="9-9", nombre="Otro municipio", datos={}))
        db.commit()  # misma clave en OTRO municipio de la plataforma: permitido
