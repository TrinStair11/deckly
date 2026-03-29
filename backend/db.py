import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import ROOT_DIR, load_local_env

load_local_env()

DEFAULT_DATABASE_PATH = ROOT_DIR / "deckly.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _has_table(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    if not _has_table(inspector, table_name):
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    if _has_table(inspector, "decks"):
        deck_columns = {column["name"] for column in inspector.get_columns("decks")}
        if "name" not in deck_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE decks ADD COLUMN name VARCHAR"))
                if "title" in deck_columns:
                    connection.execute(text("UPDATE decks SET name = COALESCE(name, title, '')"))
        if "title" not in deck_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE decks ADD COLUMN title VARCHAR"))
                if "name" in deck_columns:
                    connection.execute(text("UPDATE decks SET title = COALESCE(name, '')"))
        _ensure_column("decks", "updated_at", "updated_at DATETIME")
        _ensure_column("decks", "visibility", "visibility VARCHAR DEFAULT 'public' NOT NULL")
        _ensure_column("decks", "password_hash", "password_hash VARCHAR")
        with engine.begin() as connection:
            connection.execute(text("UPDATE decks SET name = COALESCE(name, title, '')"))
            connection.execute(text("UPDATE decks SET title = COALESCE(title, name, '')"))
            connection.execute(text("UPDATE decks SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
            if "access_password_hash" in deck_columns:
                connection.execute(text("UPDATE decks SET password_hash = COALESCE(password_hash, access_password_hash)"))

    if _has_table(inspector, "cards"):
        _ensure_column("cards", "deck_id", "deck_id INTEGER")
        _ensure_column("cards", "image_url", "image_url VARCHAR DEFAULT '' NOT NULL")
        _ensure_column("cards", "position", "position INTEGER DEFAULT 0 NOT NULL")
        _ensure_column("cards", "created_at", "created_at DATETIME")
        _ensure_column("cards", "updated_at", "updated_at DATETIME")
        _ensure_column("cards", "deleted_at", "deleted_at DATETIME")
        with engine.begin() as connection:
            connection.execute(text("UPDATE cards SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
            connection.execute(text("UPDATE cards SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))

    if _has_table(inspector, "user_deck_progress"):
        progress_columns = {column["name"] for column in inspector.get_columns("user_deck_progress")}
        _ensure_column("user_deck_progress", "new_available_count", "new_available_count INTEGER DEFAULT 0 NOT NULL")
        _ensure_column("user_deck_progress", "due_review_count", "due_review_count INTEGER DEFAULT 0 NOT NULL")
        with engine.begin() as connection:
            new_source = "new_count" if "new_count" in progress_columns else "0"
            due_source = "due_count" if "due_count" in progress_columns else "0"
            connection.execute(text(f"UPDATE user_deck_progress SET new_available_count = COALESCE(new_available_count, {new_source}, 0)"))
            connection.execute(text(f"UPDATE user_deck_progress SET due_review_count = COALESCE(due_review_count, {due_source}, 0)"))

    if _has_table(inspector, "quiz_attempts"):
        _ensure_column("quiz_attempts", "option_order", "option_order TEXT DEFAULT '{}' NOT NULL")
