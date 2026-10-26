"""campos del indicador de la referencia: descripciones de variables, meta administración en texto,
fecha de elaboración e ID numérico

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27

upgrade:
  * `descripcion_a` / `descripcion_b` (texto de cada variable; B solo con algoritmos que la usan).
  * `meta_administracion` pasa de numérico a TEXTO libre; los valores existentes se convierten sin
    perderlos (15.0000 -> "15").
  * `fecha_elaboracion` (fecha opcional).
  * `id_numerico`: consecutivo por municipio, asignado a los indicadores existentes en orden de creación
    (`created_at`, luego `id`); único por municipio.

downgrade: quita los campos nuevos y vuelve `meta_administracion` a numérico. Los textos que no son un
número (p. ej. "15% PERSONAS ATENDIDAS LABORALMENTE.") NO caben en una columna numérica y se pierden
(quedan NULL); los que son solo un número se conservan.
"""
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def _numero_a_texto(valor) -> str | None:
    """Decimal(15.0000) -> "15", Decimal(0.5000) -> "0.5" (sin ceros de relleno ni notación científica)."""
    if valor is None:
        return None
    return format(Decimal(valor).normalize(), "f")


def _asignar_ids_numericos(bind) -> None:
    ind = sa.Table("indicador", sa.MetaData(), autoload_with=bind)
    filas = bind.execute(sa.select(ind.c.id, ind.c.municipio_id).order_by(
        ind.c.municipio_id, ind.c.created_at, ind.c.id)).fetchall()
    siguiente: dict = {}
    for f in filas:
        siguiente[f.municipio_id] = siguiente.get(f.municipio_id, 0) + 1
        bind.execute(ind.update().where(ind.c.id == f.id).values(id_numerico=siguiente[f.municipio_id]))


def upgrade() -> None:
    with op.batch_alter_table("indicador") as b:
        b.add_column(sa.Column("descripcion_a", sa.Text(), nullable=False, server_default=""))
        b.add_column(sa.Column("descripcion_b", sa.Text(), nullable=True))
        b.add_column(sa.Column("fecha_elaboracion", sa.Date(), nullable=True))
        b.add_column(sa.Column("id_numerico", sa.Integer(), nullable=True))
        b.add_column(sa.Column("meta_administracion_txt", sa.Text(), nullable=True))
    bind = op.get_bind()
    ind = sa.Table("indicador", sa.MetaData(), autoload_with=bind)
    for f in bind.execute(sa.select(ind.c.id, ind.c.meta_administracion)).fetchall():
        if f.meta_administracion is not None:
            bind.execute(ind.update().where(ind.c.id == f.id).values(
                meta_administracion_txt=_numero_a_texto(f.meta_administracion)))
    _asignar_ids_numericos(bind)
    with op.batch_alter_table("indicador") as b:
        b.drop_column("meta_administracion")
        b.alter_column("meta_administracion_txt", new_column_name="meta_administracion")
        b.alter_column("id_numerico", existing_type=sa.Integer(), nullable=False)
        b.create_unique_constraint("uq_indicador_municipio_id_numerico", ["municipio_id", "id_numerico"])


def downgrade() -> None:
    with op.batch_alter_table("indicador") as b:
        b.drop_constraint("uq_indicador_municipio_id_numerico", type_="unique")
        b.add_column(sa.Column("meta_administracion_num", sa.Numeric(18, 4), nullable=True))
    bind = op.get_bind()
    ind = sa.Table("indicador", sa.MetaData(), autoload_with=bind)
    for f in bind.execute(sa.select(ind.c.id, ind.c.meta_administracion)).fetchall():
        try:
            valor = Decimal(f.meta_administracion.strip()) if f.meta_administracion else None
        except InvalidOperation:
            valor = None  # texto que no es un número: no cabe en la columna numérica
        if valor is not None:
            bind.execute(ind.update().where(ind.c.id == f.id).values(meta_administracion_num=valor))
    with op.batch_alter_table("indicador") as b:
        b.drop_column("meta_administracion")
        b.alter_column("meta_administracion_num", new_column_name="meta_administracion")
        b.drop_column("id_numerico")
        b.drop_column("fecha_elaboracion")
        b.drop_column("descripcion_b")
        b.drop_column("descripcion_a")
