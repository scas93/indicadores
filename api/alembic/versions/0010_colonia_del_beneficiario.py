"""Fase 4.3a: colonia del beneficiario ligada (opcionalmente) al catálogo de Colonias

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-04

upgrade: `beneficiario.colonia_id` (nulo = colonia escrita a mano, como hasta ahora).
downgrade: la quita.
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("beneficiario") as b:
        b.add_column(sa.Column("colonia_id", sa.Uuid(), nullable=True))
        b.create_foreign_key("fk_beneficiario_colonia", "colonia", ["colonia_id"], ["id"])
        b.create_index("ix_beneficiario_colonia_id", ["colonia_id"])


def downgrade() -> None:
    with op.batch_alter_table("beneficiario") as b:
        b.drop_index("ix_beneficiario_colonia_id")
        b.drop_constraint("fk_beneficiario_colonia", type_="foreignkey")
        b.drop_column("colonia_id")
