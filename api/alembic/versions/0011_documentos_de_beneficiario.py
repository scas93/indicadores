"""Fase 4.3b: documentos adjuntos de beneficiarios (el archivo vive en un bucket privado)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-04

upgrade: tabla `documento_beneficiario` (tipo, título, observaciones, llave del archivo, tipo MIME y tamaño).
downgrade: la quita (los archivos del bucket no se tocan).
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documento_beneficiario",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("municipio_id", sa.Uuid(), sa.ForeignKey("municipio.id"), nullable=False, index=True),
        sa.Column("beneficiario_id", sa.Uuid(), sa.ForeignKey("beneficiario.id"), nullable=False, index=True),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("observaciones", sa.Text()),
        sa.Column("llave", sa.Text(), nullable=False),
        sa.Column("nombre_archivo", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("documento_beneficiario")
