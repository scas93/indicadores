"""ejes generales: el eje deja de pertenecer a un centro gestor

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27

La planeación queda en dos ramas independientes: Eje → Subtema → Estrategia → Programa y
Centro gestor → Programa.

upgrade:
  1. Si en un municipio hay ejes con la misma clave (hoy podían repetirse bajo distintos centros
     gestores), se fusionan en uno: se conserva el activo (si hay varios, el de menor id), los subtemas
     de los demás se repuntan a ese y los sobrantes se eliminan.
  2. Se quita `eje.centro_gestor_id` (y su índice) y la unicidad pasa de (municipio, centro_gestor,
     clave) a (municipio, clave).

downgrade (SIN pérdida de estructura pero NO reconstruye el centro gestor original, que ya no se
guarda): cada eje recibe el primer centro gestor del municipio (por clave). Falla con un mensaje claro
si un municipio tiene ejes y ningún centro gestor.
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def _fusionar_ejes_duplicados(bind) -> None:
    eje = sa.Table("eje", sa.MetaData(), autoload_with=bind)
    subtema = sa.Table("subtema", sa.MetaData(), autoload_with=bind)
    filas = bind.execute(sa.select(eje.c.id, eje.c.municipio_id, eje.c.clave, eje.c.activo)).fetchall()
    grupos: dict = {}
    for f in filas:
        grupos.setdefault((f.municipio_id, f.clave), []).append(f)
    for dup in grupos.values():
        if len(dup) < 2:
            continue
        # se conserva el activo y, entre iguales, el de menor id (determinista)
        dup.sort(key=lambda f: (not f.activo, str(f.id)))
        conservado, sobrantes = dup[0], dup[1:]
        ids = [f.id for f in sobrantes]
        bind.execute(subtema.update().where(subtema.c.eje_id.in_(ids)).values(eje_id=conservado.id))
        bind.execute(eje.delete().where(eje.c.id.in_(ids)))


def upgrade() -> None:
    _fusionar_ejes_duplicados(op.get_bind())
    with op.batch_alter_table("eje") as b:
        b.drop_index("ix_eje_centro_gestor_id")
        b.drop_column("centro_gestor_id")  # en Postgres arrastra la unicidad anterior; en SQLite la recrea la tabla
        b.create_unique_constraint("uq_eje_municipio_clave", ["municipio_id", "clave"])


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("eje") as b:
        b.drop_constraint("uq_eje_municipio_clave", type_="unique")
        b.add_column(sa.Column("centro_gestor_id", sa.Uuid(), nullable=True))
    eje = sa.Table("eje", sa.MetaData(), autoload_with=bind)
    centro = sa.Table("centro_gestor", sa.MetaData(), autoload_with=bind)
    for m in {f.municipio_id for f in bind.execute(sa.select(eje.c.municipio_id)).fetchall()}:
        primero = bind.execute(sa.select(centro.c.id).where(centro.c.municipio_id == m)
                               .order_by(centro.c.clave).limit(1)).scalar()
        if primero is None:
            raise RuntimeError(f"No se puede revertir: el municipio {m} tiene ejes y ningún centro gestor al cual asignarlos")
        bind.execute(eje.update().where(eje.c.municipio_id == m).values(centro_gestor_id=primero))
    with op.batch_alter_table("eje") as b:
        b.alter_column("centro_gestor_id", existing_type=sa.Uuid(), nullable=False)
        b.create_foreign_key("fk_eje_centro_gestor", "centro_gestor", ["centro_gestor_id"], ["id"])
        b.create_index("ix_eje_centro_gestor_id", ["centro_gestor_id"])
        b.create_unique_constraint("eje_municipio_id_centro_gestor_id_clave_key", ["municipio_id", "centro_gestor_id", "clave"])
