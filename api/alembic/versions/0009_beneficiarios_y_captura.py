"""Fase 4.2: beneficiarios y captura de apoyos

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-04

upgrade: tablas `beneficiario` (CURP única por municipio) y `captura_apoyo` (vacías).
downgrade: las quita.
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def _utc():
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "beneficiario",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("municipio_id", sa.Uuid(), sa.ForeignKey("municipio.id"), nullable=False, index=True),
        sa.Column("curp", sa.String(32), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("fecha_nacimiento", sa.Date()),
        sa.Column("genero", sa.String(1)),
        sa.Column("cp", sa.String(10)),
        sa.Column("estado_id", sa.Uuid(), sa.ForeignKey("geografia_estado.id"), index=True),
        sa.Column("municipio_geo_id", sa.Uuid(), sa.ForeignKey("catalogo_municipio.id"), index=True),
        sa.Column("localidad_id", sa.Uuid(), sa.ForeignKey("catalogo_municipio.id"), index=True),
        sa.Column("calle", sa.Text()),
        sa.Column("numero", sa.String(32)),
        sa.Column("colonia", sa.Text()),
        sa.Column("telefono", sa.String(32)),
        sa.Column("correo", sa.String(254)),
        sa.Column("es_ejemplo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", _utc(), nullable=False),
        sa.UniqueConstraint("municipio_id", "curp"),
    )
    op.create_table(
        "captura_apoyo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("municipio_id", sa.Uuid(), sa.ForeignKey("municipio.id"), nullable=False, index=True),
        sa.Column("beneficiario_id", sa.Uuid(), sa.ForeignKey("beneficiario.id"), nullable=False, index=True),
        sa.Column("programa_id", sa.Uuid(), sa.ForeignKey("programa.id"), nullable=False, index=True),
        sa.Column("apoyo_id", sa.Uuid(), sa.ForeignKey("apoyo.id"), nullable=False, index=True),
        sa.Column("descripcion_apoyo_id", sa.Uuid(), sa.ForeignKey("descripcion_apoyo.id"), index=True),
        sa.Column("nivel_socioeconomico_id", sa.Uuid(), sa.ForeignKey("catalogo_municipio.id"), index=True),
        sa.Column("grupo_edad_id", sa.Uuid(), sa.ForeignKey("catalogo_municipio.id"), index=True),
        sa.Column("edad", sa.Integer()),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fecha_entrega", sa.Date(), nullable=False, index=True),
        sa.Column("fecha_registro", sa.Date(), nullable=False, index=True),
        sa.Column("observaciones", sa.Text()),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuario.id")),
        sa.Column("es_ejemplo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", _utc(), nullable=False),
        sa.CheckConstraint("cantidad >= 1", name="ck_captura_apoyo_cantidad"),
    )


def downgrade() -> None:
    op.drop_table("captura_apoyo")
    op.drop_table("beneficiario")
