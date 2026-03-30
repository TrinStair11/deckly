import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
from tests.postgres_utils import (
    DEFAULT_RUNTIME_DATABASE_URL,
    DEFAULT_TEST_DATABASE_URL,
    create_temp_database,
    drop_database,
    ensure_database_exists,
    render_database_url,
)

TEST_ADMIN_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_RUNTIME_DATABASE_URL).strip() or DEFAULT_RUNTIME_DATABASE_URL
TEST_BOOTSTRAP_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL).strip() or DEFAULT_TEST_DATABASE_URL
ensure_database_exists(TEST_BOOTSTRAP_DATABASE_URL, TEST_ADMIN_DATABASE_URL)
os.environ["DATABASE_URL"] = TEST_BOOTSTRAP_DATABASE_URL

from backend.db import Base
from backend.auth import get_db
from backend.main import FAILED_ATTEMPTS, app


@pytest.fixture(autouse=True)
def clear_rate_limits():
    FAILED_ATTEMPTS.clear()
    yield
    FAILED_ATTEMPTS.clear()


@pytest.fixture
def db_session():
    test_database_url = create_temp_database(TEST_BOOTSTRAP_DATABASE_URL, "deckly_test")
    engine = create_engine(render_database_url(test_database_url), pool_pre_ping=True)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        drop_database(test_database_url, TEST_BOOTSTRAP_DATABASE_URL)


@pytest.fixture
def client(db_session):
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind())

    def override_get_db():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
