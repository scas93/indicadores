"""Migración 0008 (grupos de edad de la referencia): la plantilla queda con los 4 grupos y las copias de los
municipios existentes se alinean; lo que algo use no se borra. El DDL no cambia: es solo de datos."""
import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import seed
from app.models import Base, CatalogoMunicipio, Municipio, PlantillaGrupoEdad

RUTA = Path(__file__).parents[1] / "alembic/versions/0008_grupos_de_edad_de_la_referencia.py"
spec = importlib.util.spec_from_file_location("mig0008", RUTA)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

VIEJOS = [("0-11", "Niñez", 0, 11), ("12-17", "Adolescencia", 12, 17), ("18-29", "Juventud", 18, 29),
          ("30-59", "Adultez", 30, 59), ("60+", "Adultos mayores", 60, None)]
NUEVOS = [("11-17", "ADOLESCENTE", 11, 17), ("18-59", "ADULTO", 18, 59), ("2-10", "NIÑO", 2, 10),
          ("60-80", "TERCERA EDAD", 60, 80)]


def _entorno(municipios=2):
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    ids = []
    with Session(e) as db:
        for clave, nombre, mn, mx in VIEJOS:
            db.add(PlantillaGrupoEdad(clave=clave, nombre=nombre, edad_min=mn, edad_max=mx))
        for i in range(municipios):
            m = Municipio(id=uuid.uuid4(), nombre=f"M{i}", subdominio=f"m{i}")
            db.add(m)
            ids.append(m.id)
            for clave, nombre, mn, mx in VIEJOS:
                db.add(CatalogoMunicipio(id=uuid.uuid4(), municipio_id=m.id, tipo="grupo_edad", clave=clave, nombre=nombre,
                                         datos={"edad_min": mn, "edad_max": mx}))
        db.commit()
    return e, ids


def _grupos(e, mid=None):
    with Session(e) as db:
        if mid is None:
            return sorted((g.clave, g.nombre, g.edad_min, g.edad_max) for g in db.scalars(select(PlantillaGrupoEdad)))
        return sorted((g.clave, g.nombre, g.datos["edad_min"], g.datos["edad_max"]) for g in db.scalars(
            select(CatalogoMunicipio).where(CatalogoMunicipio.municipio_id == mid, CatalogoMunicipio.tipo == "grupo_edad")))


def test_el_seed_ya_trae_los_4_grupos_de_la_referencia():
    assert sorted(seed.GRUPOS_EDAD) == NUEVOS and all(mx is not None for *_, mx in seed.GRUPOS_EDAD)
    assert sorted((c, n, mn, mx) for c, n, mn, mx in mig.GRUPOS) == NUEVOS


def test_alinea_la_plantilla_y_las_copias_de_todos_los_municipios_y_cuenta_los_cambios():
    e, ids = _entorno(2)
    with e.begin() as c:
        r = mig._alinear_grupos(c)
    assert _grupos(e) == NUEVOS and all(_grupos(e, i) == NUEVOS for i in ids)
    assert (r["plantilla_quitados"], r["plantilla_agregados"]) == (5, 4)
    assert (r["copias_quitadas"], r["copias_agregadas"]) == (10, 8)  # 5 quitadas y 4 agregadas por municipio
    assert r["total_cambiados"] == 5 + 4 + 10 + 8 and r["copias_en_uso_conservadas"] == []


def test_es_idempotente():
    e, _ = _entorno(1)
    with e.begin() as c:
        mig._alinear_grupos(c)
    with e.begin() as c:
        assert mig._alinear_grupos(c)["total_cambiados"] == 0


def test_corrige_un_grupo_con_la_clave_correcta_pero_otro_rango():
    e, ids = _entorno(1)
    with Session(e) as db:
        db.add(CatalogoMunicipio(id=uuid.uuid4(), municipio_id=ids[0], tipo="grupo_edad", clave="18-59", nombre="Adultos",
                                 datos={"edad_min": 18, "edad_max": 60}))
        db.commit()
    with e.begin() as c:
        r = mig._alinear_grupos(c)
    assert r["copias_actualizadas"] == 1 and _grupos(e, ids[0]) == NUEVOS


def test_un_grupo_en_uso_no_se_borra_y_se_reporta():
    e, ids = _entorno(2)
    entrega = sa.Table("entrega", sa.MetaData(), sa.Column("id", sa.Uuid, primary_key=True), sa.Column("grupo_edad_id", sa.Uuid))
    entrega.create(e)
    with Session(e) as db:
        usado = db.scalar(select(CatalogoMunicipio).where(CatalogoMunicipio.municipio_id == ids[0], CatalogoMunicipio.clave == "12-17"))
        db.execute(entrega.insert().values(id=uuid.uuid4(), grupo_edad_id=usado.id))
        db.commit()
    with e.begin() as c:
        r = mig._alinear_grupos(c)
    assert r["copias_en_uso_conservadas"] == [{"municipio_id": str(ids[0]), "clave": "12-17"}]
    assert ("12-17", "Adolescencia", 12, 17) in _grupos(e, ids[0])      # conservado
    assert set(NUEVOS) <= set(_grupos(e, ids[0]))                       # y aun así recibe los 4
    assert _grupos(e, ids[1]) == NUEVOS                                 # el otro municipio, limpio
