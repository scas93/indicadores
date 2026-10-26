"""Migración 0004 (ejes generales): la fusión de ejes con la misma clave y el repunte de subtemas.
La migración completa (DDL) se verifica en CI con `alembic upgrade head` sobre Postgres."""
import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa

RUTA = Path(__file__).parents[1] / "alembic/versions/0004_ejes_generales.py"
spec = importlib.util.spec_from_file_location("mig0004", RUTA)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def _base():
    e = sa.create_engine("sqlite://")
    md = sa.MetaData()
    eje = sa.Table("eje", md, sa.Column("id", sa.Uuid, primary_key=True), sa.Column("municipio_id", sa.Uuid),
                   sa.Column("clave", sa.String), sa.Column("activo", sa.Boolean), sa.Column("centro_gestor_id", sa.Uuid))
    subtema = sa.Table("subtema", md, sa.Column("id", sa.Uuid, primary_key=True), sa.Column("eje_id", sa.Uuid))
    md.create_all(e)
    return e, eje, subtema


def test_fusiona_ejes_con_la_misma_clave_conserva_el_activo_y_repunta_subtemas():
    e, eje, subtema = _base()
    m1, m2, cg1, cg2 = (uuid.uuid4() for _ in range(4))
    inactivo, activo, otro, ajeno = (uuid.uuid4() for _ in range(4))
    s1, s2, s3, s4 = (uuid.uuid4() for _ in range(4))
    with e.begin() as c:
        c.execute(eje.insert(), [
            dict(id=inactivo, municipio_id=m1, clave="E1", activo=False, centro_gestor_id=cg1),
            dict(id=activo, municipio_id=m1, clave="E1", activo=True, centro_gestor_id=cg2),
            dict(id=otro, municipio_id=m1, clave="E2", activo=True, centro_gestor_id=cg1),
            dict(id=ajeno, municipio_id=m2, clave="E1", activo=True, centro_gestor_id=cg1)])
        c.execute(subtema.insert(), [dict(id=s1, eje_id=inactivo), dict(id=s2, eje_id=activo),
                                     dict(id=s3, eje_id=otro), dict(id=s4, eje_id=ajeno)])
        mig._fusionar_ejes_duplicados(c)
    with e.connect() as c:
        ejes = {r.id for r in c.execute(sa.select(eje.c.id))}
        assert ejes == {activo, otro, ajeno}  # el inactivo duplicado desaparece; otro municipio intacto
        sub = {r.id: r.eje_id for r in c.execute(sa.select(subtema.c.id, subtema.c.eje_id))}
        assert sub == {s1: activo, s2: activo, s3: otro, s4: ajeno}  # nada queda apuntando a un eje borrado


def test_sin_duplicados_no_cambia_nada():
    e, eje, _ = _base()
    m, cg = uuid.uuid4(), uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(3)]
    with e.begin() as c:
        c.execute(eje.insert(), [dict(id=i, municipio_id=m, clave=f"E{k}", activo=True, centro_gestor_id=cg)
                                 for k, i in enumerate(ids)])
        mig._fusionar_ejes_duplicados(c)
    with e.connect() as c:
        assert {r.id for r in c.execute(sa.select(eje.c.id))} == set(ids)
