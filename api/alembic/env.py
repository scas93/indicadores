from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.models import Base

# Logging de alembic.ini: sin esto `alembic upgrade head` no imprime nada y el log del despliegue no
# muestra qué migraciones corrieron ("Running upgrade 0003 -> 0004").
if context.config.config_file_name:
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata
url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
