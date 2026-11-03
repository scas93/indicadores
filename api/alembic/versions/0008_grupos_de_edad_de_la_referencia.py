"""grupos de edad de la referencia: la plantilla pasa a 4 grupos y los municipios existentes se alinean

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-03

La plantilla traía 5 grupos (0-11, 12-17, 18-29, 30-59 y 60+); el sistema de referencia usa 4, todos con
máximo definido: NIÑO (2-10), ADOLESCENTE (11-17), ADULTO (18-59) y TERCERA EDAD (60-80).

upgrade:
  * `plantilla_grupo_edad`: queda exactamente con esos 4 (se quitan los demás y se agregan los que falten).
  * Copias de cada municipio (`catalogo_municipio`, tipo grupo_edad): se reemplazan por los 4. Un grupo que
    algo use (hoy nada: no existen las entregas) NO se borra: se conserva y se reporta. Si existe la tabla
    `entrega` con `grupo_edad_id` (Fase 5, parte 2), esa referencia cuenta como uso.
  * Imprime cuántos registros cambió.

downgrade: no revierte datos (no hay forma de saber qué grupos tenía cada municipio antes).
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

GRUPOS = [("2-10", "NIÑO", 2, 10), ("11-17", "ADOLESCENTE", 11, 17),
          ("18-59", "ADULTO", 18, 59), ("60-80", "TERCERA EDAD", 60, 80)]


def _en_uso(bind, grupo_id) -> int:
    """Cuántas entregas usan el grupo (0 mientras la tabla `entrega` no exista)."""
    insp = sa.inspect(bind)
    if not insp.has_table("entrega") or "grupo_edad_id" not in {c["name"] for c in insp.get_columns("entrega")}:
        return 0
    entrega = sa.Table("entrega", sa.MetaData(), sa.Column("grupo_edad_id", sa.Uuid()))
    return bind.execute(sa.select(sa.func.count()).select_from(entrega).where(entrega.c.grupo_edad_id == grupo_id)).scalar_one()


def _alinear_grupos(bind) -> dict:
    md = sa.MetaData()
    U, S, T = sa.Uuid(), sa.String(), sa.Text()
    plantilla = sa.Table("plantilla_grupo_edad", md, sa.Column("id", U), sa.Column("clave", S), sa.Column("nombre", T),
                         sa.Column("edad_min", sa.Integer), sa.Column("edad_max", sa.Integer))
    cat = sa.Table("catalogo_municipio", md, sa.Column("id", U), sa.Column("municipio_id", U), sa.Column("tipo", S),
                   sa.Column("clave", S), sa.Column("nombre", T), sa.Column("datos", sa.JSON().with_variant(JSONB(), "postgresql")))
    municipio = sa.Table("municipio", md, sa.Column("id", U))
    claves = {g[0] for g in GRUPOS}
    r = {"plantilla_quitados": 0, "plantilla_agregados": 0, "plantilla_actualizados": 0,
         "copias_quitadas": 0, "copias_agregadas": 0, "copias_actualizadas": 0, "copias_en_uso_conservadas": []}

    # --- plantilla global
    actuales = {f.clave: f for f in bind.execute(sa.select(plantilla)).all()}
    for clave, f in actuales.items():
        if clave not in claves:
            bind.execute(plantilla.delete().where(plantilla.c.id == f.id))
            r["plantilla_quitados"] += 1
    for clave, nombre, mn, mx in GRUPOS:
        f = actuales.get(clave)
        if f is None:
            bind.execute(plantilla.insert().values(id=uuid.uuid4(), clave=clave, nombre=nombre, edad_min=mn, edad_max=mx))
            r["plantilla_agregados"] += 1
        elif (f.nombre, f.edad_min, f.edad_max) != (nombre, mn, mx):
            bind.execute(plantilla.update().where(plantilla.c.id == f.id).values(nombre=nombre, edad_min=mn, edad_max=mx))
            r["plantilla_actualizados"] += 1

    # --- copias de cada municipio
    for mid in [m.id for m in bind.execute(sa.select(municipio.c.id)).all()]:
        copias = {c.clave: c for c in bind.execute(sa.select(cat).where(cat.c.municipio_id == mid, cat.c.tipo == "grupo_edad")).all()}
        for clave, c in copias.items():
            if clave in claves:
                continue
            if _en_uso(bind, c.id):
                r["copias_en_uso_conservadas"].append({"municipio_id": str(mid), "clave": clave})
                continue
            bind.execute(cat.delete().where(cat.c.id == c.id))
            r["copias_quitadas"] += 1
        for clave, nombre, mn, mx in GRUPOS:
            c = copias.get(clave)
            datos = {"edad_min": mn, "edad_max": mx}
            if c is None:
                bind.execute(cat.insert().values(id=uuid.uuid4(), municipio_id=mid, tipo="grupo_edad", clave=clave,
                                                 nombre=nombre, datos=datos))
                r["copias_agregadas"] += 1
            elif (c.nombre, c.datos) != (nombre, datos):
                bind.execute(cat.update().where(cat.c.id == c.id).values(nombre=nombre, datos=datos))
                r["copias_actualizadas"] += 1
    r["total_cambiados"] = sum(v for k, v in r.items() if isinstance(v, int))
    return r


def upgrade() -> None:
    r = _alinear_grupos(op.get_bind())
    print(f"[0008] grupos de edad: {r['total_cambiados']} registros cambiados {r}")
    if r["copias_en_uso_conservadas"]:
        print(f"[0008] ATENCIÓN: grupos en uso que NO se borraron: {r['copias_en_uso_conservadas']}")


def downgrade() -> None:
    pass
