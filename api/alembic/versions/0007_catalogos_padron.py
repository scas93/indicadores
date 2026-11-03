"""Fase 5 (parte 1): catálogos del Padrón

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-03

upgrade:
  * Tablas `apoyo`, `descripcion_apoyo` y `colonia` (vacías: el municipio las llena).
  * Índice único parcial sobre `catalogo_municipio` (municipio, tipo, clave) para los catálogos planos
    del Padrón (municipios, grupos de edad y niveles socioeconómicos), porque `padre_id` NULL no cuenta
    en la restricción única original.
  * Completa en los municipios YA creados las copias de plantilla que falten (grupos de edad, niveles
    socioeconómicos y, si el municipio tiene estado, sus municipios y localidades). Solo agrega lo que
    falta: no toca ni sobrescribe lo existente. Imprime cuántas filas agregó.

downgrade: quita las tres tablas y el índice (las copias agregadas a `catalogo_municipio` se conservan).
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

PLANOS = "tipo IN ('geo_municipio', 'grupo_edad', 'nivel_socioeconomico')"


def _completar_copias(bind) -> dict[str, int]:
    md = sa.MetaData()
    U, S, T = sa.Uuid(), sa.String(), sa.Text()
    datos_tipo = sa.JSON().with_variant(JSONB(), "postgresql")
    mun = sa.Table("municipio", md, sa.Column("id", U), sa.Column("estado_republica_id", U))
    cat = sa.Table("catalogo_municipio", md, sa.Column("id", U), sa.Column("municipio_id", U), sa.Column("tipo", S),
                   sa.Column("clave", S), sa.Column("nombre", T), sa.Column("padre_id", U), sa.Column("datos", datos_tipo))
    t = {
        "plantilla_grupo_edad": sa.Table("plantilla_grupo_edad", md, sa.Column("clave", S), sa.Column("nombre", T),
                                         sa.Column("edad_min", sa.Integer), sa.Column("edad_max", sa.Integer)),
        "plantilla_nivel_socioeconomico": sa.Table("plantilla_nivel_socioeconomico", md, sa.Column("clave", S),
                                                   sa.Column("nombre", T)),
        "geografia_municipio": sa.Table("geografia_municipio", md, sa.Column("id", U), sa.Column("estado_id", U),
                                        sa.Column("clave", S), sa.Column("nombre", T)),
        "geografia_localidad": sa.Table("geografia_localidad", md, sa.Column("municipio_geo_id", U),
                                        sa.Column("clave", S), sa.Column("nombre", T)),
    }
    agregadas = {"grupo_edad": 0, "nivel_socioeconomico": 0, "geo_municipio": 0, "geo_localidad": 0}

    def claves(mid, tipo):
        return {r.clave for r in bind.execute(sa.select(cat.c.clave).where(cat.c.municipio_id == mid, cat.c.tipo == tipo))}

    for m in bind.execute(sa.select(mun.c.id, mun.c.estado_republica_id)).all():
        for tipo, plantilla, extras in (("grupo_edad", t["plantilla_grupo_edad"], ("edad_min", "edad_max")),
                                        ("nivel_socioeconomico", t["plantilla_nivel_socioeconomico"], ())):
            tengo = claves(m.id, tipo)
            for f in bind.execute(sa.select(plantilla)).all():
                if f.clave not in tengo:
                    bind.execute(cat.insert().values(
                        id=uuid.uuid4(), municipio_id=m.id, tipo=tipo, clave=f.clave, nombre=f.nombre,
                        datos={k: getattr(f, k) for k in extras}))
                    agregadas[tipo] += 1
        if not m.estado_republica_id:
            continue
        tengo = claves(m.id, "geo_municipio")
        ids_nuevos = {}
        for g in bind.execute(sa.select(t["geografia_municipio"]).where(
                t["geografia_municipio"].c.estado_id == m.estado_republica_id)).all():
            if g.clave in tengo:
                ids_nuevos[g.id] = bind.execute(sa.select(cat.c.id).where(
                    cat.c.municipio_id == m.id, cat.c.tipo == "geo_municipio", cat.c.clave == g.clave)).scalar_one()
                continue
            nuevo = uuid.uuid4()
            bind.execute(cat.insert().values(id=nuevo, municipio_id=m.id, tipo="geo_municipio", clave=g.clave,
                                             nombre=g.nombre, datos={}))
            ids_nuevos[g.id] = nuevo
            agregadas["geo_municipio"] += 1
        if not ids_nuevos:
            continue
        existentes = {(r.padre_id, r.clave) for r in bind.execute(sa.select(cat.c.padre_id, cat.c.clave).where(
            cat.c.municipio_id == m.id, cat.c.tipo == "geo_localidad"))}
        for l in bind.execute(sa.select(t["geografia_localidad"]).where(
                t["geografia_localidad"].c.municipio_geo_id.in_(list(ids_nuevos)))).all():
            padre = ids_nuevos[l.municipio_geo_id]
            if (padre, l.clave) in existentes:
                continue
            bind.execute(cat.insert().values(id=uuid.uuid4(), municipio_id=m.id, tipo="geo_localidad", clave=l.clave,
                                             nombre=l.nombre, padre_id=padre, datos={}))
            agregadas["geo_localidad"] += 1
    return agregadas


def upgrade() -> None:
    def base_tabla(nombre, *cols):
        op.create_table(
            nombre,
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('clave', sa.String(length=32), nullable=False),
            sa.Column('nombre', sa.Text(), nullable=False),
            *cols,
            sa.Column('municipio_id', sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('municipio_id', 'clave'))
        op.create_index(op.f(f'ix_{nombre}_municipio_id'), nombre, ['municipio_id'], unique=False)

    base_tabla('apoyo', sa.Column('programa_id', sa.Uuid(), nullable=False), sa.Column('observaciones', sa.Text()),
               sa.ForeignKeyConstraint(['programa_id'], ['programa.id']))
    op.create_index(op.f('ix_apoyo_programa_id'), 'apoyo', ['programa_id'], unique=False)
    base_tabla('descripcion_apoyo', sa.Column('apoyo_id', sa.Uuid(), nullable=False), sa.Column('observaciones', sa.Text()),
               sa.ForeignKeyConstraint(['apoyo_id'], ['apoyo.id']))
    op.create_index(op.f('ix_descripcion_apoyo_apoyo_id'), 'descripcion_apoyo', ['apoyo_id'], unique=False)
    base_tabla('colonia', sa.Column('estado_id', sa.Uuid(), nullable=False),
               sa.Column('municipio_geo_id', sa.Uuid(), nullable=False),
               sa.ForeignKeyConstraint(['estado_id'], ['geografia_estado.id']),
               sa.ForeignKeyConstraint(['municipio_geo_id'], ['catalogo_municipio.id']))
    op.create_index(op.f('ix_colonia_estado_id'), 'colonia', ['estado_id'], unique=False)
    op.create_index(op.f('ix_colonia_municipio_geo_id'), 'colonia', ['municipio_geo_id'], unique=False)

    agregadas = _completar_copias(op.get_bind())
    print(f"[0007] copias de plantilla agregadas a municipios existentes: {agregadas}")
    op.create_index('uq_catalogo_municipio_clave_plano', 'catalogo_municipio', ['municipio_id', 'tipo', 'clave'],
                    unique=True, postgresql_where=sa.text(PLANOS), sqlite_where=sa.text(PLANOS))


def downgrade() -> None:
    op.drop_index('uq_catalogo_municipio_clave_plano', table_name='catalogo_municipio')
    op.drop_table('colonia')
    op.drop_table('descripcion_apoyo')
    op.drop_table('apoyo')
