from sqlalchemy import create_engine, text

from backend.db import ensure_schema


def test_ensure_schema_adds_shared_deck_and_card_columns(tmp_path, monkeypatch):
    database_path = tmp_path / "migration.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL, password_hash VARCHAR NOT NULL, created_at DATETIME)"))
        connection.execute(text("CREATE TABLE decks (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, description VARCHAR DEFAULT '' NOT NULL, created_at DATETIME, owner_id INTEGER NOT NULL)"))
        connection.execute(text("CREATE TABLE cards (id INTEGER PRIMARY KEY, front VARCHAR, back VARCHAR, owner_id INTEGER, deck_id INTEGER)"))
    monkeypatch.setattr("backend.db.engine", engine)

    ensure_schema()

    with engine.begin() as connection:
        deck_columns = {column[1] for column in connection.execute(text("PRAGMA table_info(decks)")).fetchall()}
        card_columns = {column[1] for column in connection.execute(text("PRAGMA table_info(cards)")).fetchall()}
        table_names = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}

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
    engine.dispose()


def test_ensure_schema_adds_legacy_deck_name_column_when_missing(tmp_path, monkeypatch):
    database_path = tmp_path / "migration_title_only.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL, password_hash VARCHAR NOT NULL, created_at DATETIME)"))
        connection.execute(
            text(
                "CREATE TABLE decks ("
                "id INTEGER PRIMARY KEY, "
                "title VARCHAR NOT NULL, "
                "description VARCHAR DEFAULT '' NOT NULL, "
                "created_at DATETIME, "
                "owner_id INTEGER NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO decks (id, title, description, created_at, owner_id) VALUES (1, 'Title only', '', CURRENT_TIMESTAMP, 1)"))
    monkeypatch.setattr("backend.db.engine", engine)

    ensure_schema()

    with engine.begin() as connection:
        deck_columns = {column[1] for column in connection.execute(text("PRAGMA table_info(decks)")).fetchall()}
        row = connection.execute(text("SELECT name, title FROM decks WHERE id = 1")).fetchone()

    assert "name" in deck_columns
    assert row[0] == "Title only"
    assert row[1] == "Title only"
    engine.dispose()
