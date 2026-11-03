"""tipos de usuario: de 7 a 3 (informes, padron, administrador)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03

upgrade:
  * Los usuarios con un tipo retirado (presupuestacion, control_presupuestal, indicadores, alcalde) se
    DESHABILITAN y sus sesiones se revocan. No se borran ni se promueven: conservan su valor original en
    `usuario.tipo` (columna VARCHAR sin restricción), que la aplicación lee como "sin tipo" hasta que un
    administrador les asigne uno válido al volver a habilitarlos.
  * Imprime cuántos usuarios quedaron deshabilitados.

downgrade: no revierte datos (los usuarios deshabilitados siguen así; ya conservan su tipo original).
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

TIPOS_RETIRADOS = ('presupuestacion', 'control_presupuestal', 'indicadores', 'alcalde')


def _deshabilitar_tipos_retirados(bind) -> tuple[int, int]:
    """Devuelve (con tipo retirado, de ellos que estaban habilitados y ahora no)."""
    md = sa.MetaData()
    usuario = sa.Table("usuario", md, autoload_with=bind)
    sesion = sa.Table("sesion", md, autoload_with=bind)
    retirado = usuario.c.tipo.in_(TIPOS_RETIRADOS)
    ids = [r.id for r in bind.execute(sa.select(usuario.c.id).where(retirado))]
    if not ids:
        return 0, 0
    n = bind.execute(sa.select(sa.func.count()).select_from(usuario)
                     .where(retirado, usuario.c.activo.is_(True))).scalar_one()
    bind.execute(usuario.update().where(usuario.c.id.in_(ids)).values(activo=False))
    bind.execute(sesion.update().where(sesion.c.usuario_id.in_(ids), sesion.c.revoked_at.is_(None))
                 .values(revoked_at=sa.func.now()))
    return len(ids), n


def upgrade() -> None:
    total, recien = _deshabilitar_tipos_retirados(op.get_bind())
    print(f"[0006] usuarios con tipo retirado (todos quedan deshabilitados): {total}; "
          f"de ellos deshabilitados ahora: {recien}")


def downgrade() -> None:
    pass
