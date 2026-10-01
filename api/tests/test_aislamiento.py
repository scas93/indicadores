"""Capa común de aislamiento por municipio_id (tenancy.py), sin pasar por la API."""
import uuid

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import TenantViolation
from app.models import CatalogoMunicipio, Municipio, TipoUsuario, Usuario
from app.tenancy import scope_session


@pytest.fixture()
def dos(db):
    a = Municipio(nombre="A", subdominio="a")
    b = Municipio(nombre="B", subdominio="b")
    db.add_all([a, b])
    db.flush()
    for m in (a, b):
        db.add(Usuario(municipio_id=m.id, usuario="admin", password_encrypted="x",
                       tipo=TipoUsuario.administrador, nombre=m.nombre))
        db.add(CatalogoMunicipio(municipio_id=m.id, tipo="frecuencia", clave="m", nombre=m.nombre))
    db.commit()
    return a, b


def _scoped(engine, mid):
    return scope_session(Session(engine, expire_on_commit=False), mid)


def test_select_solo_ve_su_municipio(engine, dos):
    a, b = dos
    with _scoped(engine, a.id) as s:
        nombres = [u.nombre for u in s.scalars(select(Usuario))]
        assert nombres == ["A"]
        assert [c.nombre for c in s.scalars(select(CatalogoMunicipio))] == ["A"]


def test_get_por_id_de_otro_municipio_devuelve_none(engine, dos, db):
    a, b = dos
    id_de_b = db.scalar(select(Usuario.id).where(Usuario.municipio_id == b.id))
    with _scoped(engine, a.id) as s:
        assert s.get(Usuario, id_de_b) is None
        # ni siquiera escribiendo el filtro a mano se ve lo de B
        assert s.scalar(select(Usuario).where(Usuario.id == id_de_b)) is None


def test_update_y_delete_masivos_tambien_se_filtran(engine, dos, db):
    a, b = dos
    with _scoped(engine, a.id) as s:
        s.execute(update(Usuario).values(nombre="HACKEADO"))
        s.commit()
    nombres = dict(db.execute(select(Municipio.nombre, Usuario.nombre).join(
        Usuario, Usuario.municipio_id == Municipio.id)).all())
    assert nombres == {"A": "HACKEADO", "B": "B"}


def test_insert_hereda_municipio_de_la_sesion(engine, dos):
    a, _ = dos
    with _scoped(engine, a.id) as s:
        u = Usuario(usuario="nuevo", password_encrypted="x", tipo=TipoUsuario.informes, nombre="N")
        s.add(u)
        s.commit()
        assert u.municipio_id == a.id


def test_insert_en_otro_municipio_se_rechaza(engine, dos):
    a, b = dos
    with _scoped(engine, a.id) as s:
        s.add(Usuario(municipio_id=b.id, usuario="x", password_encrypted="x",
                      tipo=TipoUsuario.informes, nombre="X"))
        with pytest.raises(TenantViolation):
            s.commit()


def test_mover_registro_a_otro_municipio_se_rechaza(engine, dos):
    a, b = dos
    with _scoped(engine, a.id) as s:
        u = s.scalar(select(Usuario))
        u.municipio_id = b.id
        with pytest.raises(TenantViolation):
            s.commit()


def test_sesion_sin_scope_ve_todo(engine, dos, db):
    assert db.scalar(select(Usuario.id).limit(1)) is not None
    assert len(db.scalars(select(Usuario)).all()) == 2


def test_tablas_no_tenant_no_se_filtran(engine, dos):
    a, _ = dos
    with _scoped(engine, a.id) as s:
        assert len(s.scalars(select(Municipio)).all()) == 2  # municipio no es TenantMixin


def test_usuario_unico_por_municipio_no_global(db, dos):
    a, b = dos  # ambos ya tienen 'admin': mismo nombre en municipios distintos es válido
    assert db.query(Usuario).filter_by(usuario="admin").count() == 2
    from sqlalchemy.exc import IntegrityError
    db.add(Usuario(municipio_id=a.id, usuario="admin", password_encrypted="x",
                   tipo=TipoUsuario.informes, nombre="dup"))
    with pytest.raises(IntegrityError):
        db.commit()
