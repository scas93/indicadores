"""fase 1 acceso y planeacion

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02 10:09:44.567058
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- tablas y columnas nuevas ---
    op.create_table('centro_gestor',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'clave')
    )
    op.create_index(op.f('ix_centro_gestor_municipio_id'), 'centro_gestor', ['municipio_id'], unique=False)
    op.create_table('clasificacion_programatica',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'clave')
    )
    op.create_index(op.f('ix_clasificacion_programatica_municipio_id'), 'clasificacion_programatica', ['municipio_id'], unique=False)
    op.create_table('frecuencia',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'clave')
    )
    op.create_index(op.f('ix_frecuencia_municipio_id'), 'frecuencia', ['municipio_id'], unique=False)
    op.create_table('eje',
    sa.Column('centro_gestor_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['centro_gestor_id'], ['centro_gestor.id'], ),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'centro_gestor_id', 'clave')
    )
    op.create_index(op.f('ix_eje_centro_gestor_id'), 'eje', ['centro_gestor_id'], unique=False)
    op.create_index(op.f('ix_eje_municipio_id'), 'eje', ['municipio_id'], unique=False)
    op.create_table('password_reset_token',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_token_municipio_id'), 'password_reset_token', ['municipio_id'], unique=False)
    op.create_index(op.f('ix_password_reset_token_usuario_id'), 'password_reset_token', ['usuario_id'], unique=False)
    op.create_table('subtema',
    sa.Column('eje_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['eje_id'], ['eje.id'], ),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'eje_id', 'clave')
    )
    op.create_index(op.f('ix_subtema_eje_id'), 'subtema', ['eje_id'], unique=False)
    op.create_index(op.f('ix_subtema_municipio_id'), 'subtema', ['municipio_id'], unique=False)
    op.create_table('estrategia',
    sa.Column('subtema_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.ForeignKeyConstraint(['subtema_id'], ['subtema.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'subtema_id', 'clave')
    )
    op.create_index(op.f('ix_estrategia_municipio_id'), 'estrategia', ['municipio_id'], unique=False)
    op.create_index(op.f('ix_estrategia_subtema_id'), 'estrategia', ['subtema_id'], unique=False)
    op.create_table('programa',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ejercicio_fiscal', sa.Integer(), nullable=False),
    sa.Column('clave', sa.String(length=32), nullable=False),
    sa.Column('nombre', sa.Text(), nullable=False),
    sa.Column('centro_gestor_id', sa.Uuid(), nullable=False),
    sa.Column('subtema_id', sa.Uuid(), nullable=True),
    sa.Column('estrategia_id', sa.Uuid(), nullable=True),
    sa.Column('clasificacion_programatica_id', sa.Uuid(), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['centro_gestor_id'], ['centro_gestor.id'], ),
    sa.ForeignKeyConstraint(['clasificacion_programatica_id'], ['clasificacion_programatica.id'], ),
    sa.ForeignKeyConstraint(['estrategia_id'], ['estrategia.id'], ),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.ForeignKeyConstraint(['subtema_id'], ['subtema.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('municipio_id', 'ejercicio_fiscal', 'clave')
    )
    op.create_index(op.f('ix_programa_centro_gestor_id'), 'programa', ['centro_gestor_id'], unique=False)
    op.create_index(op.f('ix_programa_ejercicio_fiscal'), 'programa', ['ejercicio_fiscal'], unique=False)
    op.create_index(op.f('ix_programa_municipio_id'), 'programa', ['municipio_id'], unique=False)
    op.create_table('usuario_programa',
    sa.Column('usuario_id', sa.Uuid(), nullable=False),
    sa.Column('programa_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('municipio_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipio.id'], ),
    sa.ForeignKeyConstraint(['programa_id'], ['programa.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('usuario_id', 'programa_id')
    )
    op.create_index(op.f('ix_usuario_programa_municipio_id'), 'usuario_programa', ['municipio_id'], unique=False)
    op.add_column('municipio', sa.Column('meses_avance_activos', postgresql.ARRAY(sa.Integer()), nullable=False, server_default=sa.text("'{}'")))
    op.add_column('municipio', sa.Column('tolerancia_semaforo', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('usuario', sa.Column('direccion', sa.Text(), nullable=True))
    op.add_column('usuario', sa.Column('telefono', sa.Text(), nullable=True))
    op.add_column('usuario', sa.Column('email', sa.Text(), nullable=True))
    op.add_column('usuario', sa.Column('anios_acceso', postgresql.ARRAY(sa.Integer()), nullable=False, server_default=sa.text("'{}'")))
    op.add_column('usuario', sa.Column('meses_acceso', postgresql.ARRAY(sa.Integer()), nullable=False, server_default=sa.text("'{}'")))

    # --- frecuencia y clasificación programática pasan de filas genéricas (catalogo_municipio) a
    # tablas propias: se migran las filas existentes (conservando el id) y se retiran de la genérica.
    for tipo, tabla in (('frecuencia', 'frecuencia'),
                        ('clasificacion_programatica', 'clasificacion_programatica')):
        op.execute(
            f"INSERT INTO {tabla} (id, municipio_id, clave, nombre, activo) "
            f"SELECT id, municipio_id, clave, nombre, true FROM catalogo_municipio WHERE tipo = '{tipo}'")
        op.execute(f"DELETE FROM catalogo_municipio WHERE tipo = '{tipo}'")


def downgrade() -> None:
    # devuelve frecuencia y clasificación programática a catalogo_municipio (las deshabilitadas
    # se conservan igual: la tabla genérica no tiene baja lógica)
    for tipo, tabla in (('frecuencia', 'frecuencia'),
                        ('clasificacion_programatica', 'clasificacion_programatica')):
        op.execute(
            "INSERT INTO catalogo_municipio (id, municipio_id, tipo, clave, nombre, datos) "
            f"SELECT id, municipio_id, '{tipo}', clave, nombre, '{{}}'::jsonb FROM {tabla}")
    op.drop_column('usuario', 'meses_acceso')
    op.drop_column('usuario', 'anios_acceso')
    op.drop_column('usuario', 'email')
    op.drop_column('usuario', 'telefono')
    op.drop_column('usuario', 'direccion')
    op.drop_column('municipio', 'tolerancia_semaforo')
    op.drop_column('municipio', 'meses_avance_activos')
    op.drop_index(op.f('ix_usuario_programa_municipio_id'), table_name='usuario_programa')
    op.drop_table('usuario_programa')
    op.drop_index(op.f('ix_programa_municipio_id'), table_name='programa')
    op.drop_index(op.f('ix_programa_ejercicio_fiscal'), table_name='programa')
    op.drop_index(op.f('ix_programa_centro_gestor_id'), table_name='programa')
    op.drop_table('programa')
    op.drop_index(op.f('ix_estrategia_subtema_id'), table_name='estrategia')
    op.drop_index(op.f('ix_estrategia_municipio_id'), table_name='estrategia')
    op.drop_table('estrategia')
    op.drop_index(op.f('ix_subtema_municipio_id'), table_name='subtema')
    op.drop_index(op.f('ix_subtema_eje_id'), table_name='subtema')
    op.drop_table('subtema')
    op.drop_index(op.f('ix_password_reset_token_usuario_id'), table_name='password_reset_token')
    op.drop_index(op.f('ix_password_reset_token_municipio_id'), table_name='password_reset_token')
    op.drop_table('password_reset_token')
    op.drop_index(op.f('ix_eje_municipio_id'), table_name='eje')
    op.drop_index(op.f('ix_eje_centro_gestor_id'), table_name='eje')
    op.drop_table('eje')
    op.drop_index(op.f('ix_frecuencia_municipio_id'), table_name='frecuencia')
    op.drop_table('frecuencia')
    op.drop_index(op.f('ix_clasificacion_programatica_municipio_id'), table_name='clasificacion_programatica')
    op.drop_table('clasificacion_programatica')
    op.drop_index(op.f('ix_centro_gestor_municipio_id'), table_name='centro_gestor')
    op.drop_table('centro_gestor')

