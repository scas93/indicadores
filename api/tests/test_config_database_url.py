"""La URL de la base se normaliza para psycopg 3 (Railway entrega postgresql:// o postgres://)."""
import pytest

from app.config import Settings, normalizar_database_url


@pytest.mark.parametrize("entrada,esperada", [
    ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("  postgresql://u:p@host/db\n", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),   # ya normalizada: igual
    ("postgresql+psycopg2://u:p@host/db", "postgresql+psycopg2://u:p@host/db"),  # driver explícito: se respeta
    ("sqlite:///x.db", "sqlite:///x.db"),
    ("sqlite://", "sqlite://"),
])
def test_normalizar_database_url(entrada, esperada):
    assert normalizar_database_url(entrada) == esperada


def test_la_variable_de_entorno_tal_cual_la_da_railway_queda_normalizada(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h.railway.internal:5432/railway")
    assert Settings().database_url == "postgresql+psycopg://u:p@h.railway.internal:5432/railway"
