import os

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.db import ensure_schema, validate_database_url
from tests.postgres_utils import DEFAULT_TEST_DATABASE_URL, create_temp_database, drop_database, render_database_url

TEST_BOOTSTRAP_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL).strip() or DEFAULT_TEST_DATABASE_URL


def test_validate_database_url_rejects_sqlite():
    with pytest.raises(RuntimeError, match="SQLite is no longer supported"):
        validate_database_url("sqlite:///./deckly.db")


def test_ensure_schema_adds_shared_deck_and_card_columns(monkeypatch):
    database_url = create_temp_database(TEST_BOOTSTRAP_DATABASE_URL, "deckly_schema_test")
    engine = create_engine(render_database_url(database_url), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users ("
                    "id SERIAL PRIMARY KEY, "
                    "email VARCHAR NOT NULL, "
                    "password_hash VARCHAR NOT NULL, "
                    "created_at TIMESTAMP WITH TIME ZONE)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE decks ("
                    "id SERIAL PRIMARY KEY, "
                    "name VARCHAR NOT NULL, "
                    "description VARCHAR DEFAULT '' NOT NULL, "
                    "created_at TIMESTAMP WITH TIME ZONE, "
                    "owner_id INTEGER NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE cards ("
                    "id SERIAL PRIMARY KEY, "
                    "front VARCHAR, "
                    "back VARCHAR, "
                    "owner_id INTEGER, "
                    "deck_id INTEGER)"
                )
            )
        monkeypatch.setattr("backend.db.engine", engine)

        ensure_schema()

        inspector = inspect(engine)
        deck_columns = {column["name"] for column in inspector.get_columns("decks")}
        card_columns = {column["name"] for column in inspector.get_columns("cards")}
        table_names = set(inspector.get_table_names())

        assert "title" in deck_columns
        assert "updated_at" in deck_columns
        assert "password_hash" in deck_columns
        assert "image_url" in card_columns
        assert "position" in card_columns
        assert "created_at" in card_columns
        assert "deleted_at" in card_columns
        assert "user_saved_decks" in table_names
        assert "user_card_state" in table_names
        assert "review_logs" in table_names
        assert "user_deck_progress" in table_names
        assert "study_sessions" in table_names
    finally:
        engine.dispose()
        drop_database(database_url, TEST_BOOTSTRAP_DATABASE_URL)


def test_ensure_schema_adds_legacy_deck_name_column_when_missing(monkeypatch):
    database_url = create_temp_database(TEST_BOOTSTRAP_DATABASE_URL, "deckly_schema_test")
    engine = create_engine(render_database_url(database_url), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users ("
                    "id SERIAL PRIMARY KEY, "
                    "email VARCHAR NOT NULL, "
                    "password_hash VARCHAR NOT NULL, "
                    "created_at TIMESTAMP WITH TIME ZONE)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE decks ("
                    "id SERIAL PRIMARY KEY, "
                    "title VARCHAR NOT NULL, "
                    "description VARCHAR DEFAULT '' NOT NULL, "
                    "created_at TIMESTAMP WITH TIME ZONE, "
                    "owner_id INTEGER NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO decks (id, title, description, created_at, owner_id) "
                    "VALUES (1, 'Title only', '', CURRENT_TIMESTAMP, 1)"
                )
            )
        monkeypatch.setattr("backend.db.engine", engine)

        ensure_schema()

        inspector = inspect(engine)
        deck_columns = {column["name"] for column in inspector.get_columns("decks")}
        with engine.begin() as connection:
            row = connection.execute(text("SELECT name, title FROM decks WHERE id = 1")).fetchone()

        assert "name" in deck_columns
        assert row[0] == "Title only"
        assert row[1] == "Title only"
    finally:
        engine.dispose()
        drop_database(database_url, TEST_BOOTSTRAP_DATABASE_URL)
