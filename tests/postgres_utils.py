from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://deckly:deckly@127.0.0.1:5432/deckly_test_bootstrap"
DEFAULT_RUNTIME_DATABASE_URL = "postgresql+psycopg://deckly:deckly@127.0.0.1:5432/deckly"


def render_database_url(database_url: URL | str) -> str:
    if isinstance(database_url, URL):
        return database_url.render_as_string(hide_password=False)
    return database_url


def ensure_database_exists(database_url: URL | str, admin_database_url: URL | str) -> None:
    url = make_url(render_database_url(database_url))
    admin_engine = create_engine(render_database_url(admin_database_url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with admin_engine.connect() as connection:
        exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()


def create_temp_database(base_database_url: URL | str, prefix: str) -> URL:
    database_url = make_url(render_database_url(base_database_url)).set(database=f"{prefix}_{uuid4().hex}")
    admin_engine = create_engine(render_database_url(base_database_url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_url.database}"'))
    admin_engine.dispose()
    return database_url


def drop_database(database_url: URL | str, admin_database_url: URL | str) -> None:
    url = make_url(render_database_url(database_url))
    admin_engine = create_engine(render_database_url(admin_database_url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with admin_engine.connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": url.database},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{url.database}"'))
    admin_engine.dispose()
