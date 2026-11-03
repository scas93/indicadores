"""Migración 0006 (3 tipos de usuario): los usuarios con un tipo retirado se deshabilitan y pierden sus
sesiones, sin borrarse ni cambiar de tipo. El DDL completo se verifica en CI con `alembic upgrade head`."""
import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa

RUTA = Path(__file__).parents[1] / "alembic/versions/0006_tres_tipos_de_usuario.py"
spec = importlib.util.spec_from_file_location("mig0006", RUTA)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)


def _base():
    e = sa.create_engine("sqlite://")
    md = sa.MetaData()
    usuario = sa.Table("usuario", md, sa.Column("id", sa.Uuid, primary_key=True), sa.Column("tipo", sa.String),
                       sa.Column("activo", sa.Boolean))
    sesion = sa.Table("sesion", md, sa.Column("id", sa.Uuid, primary_key=True), sa.Column("usuario_id", sa.Uuid),
                      sa.Column("revoked_at", sa.DateTime))
    md.create_all(e)
    return e, usuario, sesion


def test_deshabilita_los_tipos_retirados_sin_borrar_ni_promover_y_revoca_sus_sesiones():
    e, usuario, sesion = _base()
    filas = {t: uuid.uuid4() for t in ("informes", "padron", "administrador", *mig.TIPOS_RETIRADOS)}
    with e.begin() as c:
        c.execute(usuario.insert(), [dict(id=i, tipo=t, activo=True) for t, i in filas.items()])
        # un retirado que ya estaba deshabilitado cuenta en el total pero no en "deshabilitados ahora"
        c.execute(usuario.update().where(usuario.c.id == filas["alcalde"]).values(activo=False))
        c.execute(sesion.insert(), [dict(id=uuid.uuid4(), usuario_id=filas["indicadores"], revoked_at=None),
                                    dict(id=uuid.uuid4(), usuario_id=filas["informes"], revoked_at=None)])
        assert mig._deshabilitar_tipos_retirados(c) == (4, 3)
    with e.connect() as c:
        u = {r.tipo: r.activo for r in c.execute(sa.select(usuario.c.tipo, usuario.c.activo))}
        assert len(u) == 7  # nadie se borró ni cambió de tipo
        assert [t for t, a in u.items() if a] == ["informes", "padron", "administrador"]
        revocadas = {r.usuario_id: r.revoked_at is not None for r in c.execute(sa.select(sesion))}
        assert revocadas == {filas["indicadores"]: True, filas["informes"]: False}


def test_sin_tipos_retirados_no_cambia_nada():
    e, usuario, _ = _base()
    with e.begin() as c:
        c.execute(usuario.insert(), [dict(id=uuid.uuid4(), tipo="informes", activo=True)])
        assert mig._deshabilitar_tipos_retirados(c) == (0, 0)
    with e.connect() as c:
        assert c.execute(sa.select(usuario.c.activo)).scalar_one() is True
