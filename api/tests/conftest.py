import base64
import os

os.environ.setdefault("PASSWORD_ENCRYPTION_KEY", base64.b64encode(b"k" * 32).decode())
os.environ["COOKIE_SECURE"] = "false"
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("UPLOAD_DIR", "/tmp/indicadores-test-uploads")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import db as app_db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

import seed  # noqa: E402

ADMIN = {"X-Ambito": "admin"}


def mun(slug: str) -> dict:
    return {"X-Municipio-Slug": slug}


@pytest.fixture()
def engine():
    """SQLite en memoria por defecto (rápido, sin infraestructura). Con TEST_DATABASE_URL
    corre contra Postgres real: las tablas se crean y destruyen por prueba."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        eng = create_engine(url)
    else:
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                            poolclass=StaticPool)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db(engine) -> Session:
    with Session(engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture()
def seeded(engine, db):
    seed.seed_super_admin(db, "root", "super-secreta", "Root")
    seed.seed_plantillas(db)
    seed.seed_reservados(db)
    db.commit()
    return db


@pytest.fixture()
def client(engine, seeded):
    get_settings.cache_clear()
    app_db.set_engine(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    """Cliente con sesión de super admin ya iniciada (cookie sesion_admin)."""
    r = client.post("/api/admin/auth/login", headers=ADMIN,
                    json={"usuario": "root", "password": "super-secreta"})
    assert r.status_code == 200, r.text
    return client


def crear_municipio(client, slug="demo", admin_usuario="admin1", password="pw1", estado=None):
    body = {"nombre": slug.title(), "subdominio": slug, "admin_nombre": "Admin " + slug,
            "admin_usuario": admin_usuario, "admin_password": password}
    if estado:
        body["estado_republica_id"] = estado
    return client.post("/api/admin/municipios", headers=ADMIN, json=body)
