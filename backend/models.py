from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship, synonym

from .db import Base
from .time_utils import now_utc


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    decks = relationship("Deck", back_populates="owner", cascade="all, delete-orphan")
    saved_deck_links = relationship("UserSavedDeck", back_populates="user", cascade="all, delete-orphan")
    card_states = relationship("UserCardState", back_populates="user", cascade="all, delete-orphan")
    review_logs = relationship("ReviewLog", back_populates="user", cascade="all, delete-orphan")
    deck_progress = relationship("UserDeckProgress", back_populates="user", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="user", cascade="all, delete-orphan")


class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True, index=True)
    # Keep legacy DB compatibility: old SQLite files enforce NOT NULL on `name`.
    name = Column(String, nullable=False)
    title = synonym("name")
    description = Column(String, default="", nullable=False)
    visibility = Column(String, default="public", nullable=False)
    password_hash = Column(String, nullable=True)
    access_password_hash = synonym("password_hash")
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="decks")
    cards = relationship("Card", back_populates="deck", cascade="all, delete-orphan")
    saved_by_links = relationship("UserSavedDeck", back_populates="deck", cascade="all, delete-orphan")
    card_states = relationship("UserCardState", back_populates="deck", cascade="all, delete-orphan")
    review_logs = relationship("ReviewLog", back_populates="deck", cascade="all, delete-orphan")
    progress_rows = relationship("UserDeckProgress", back_populates="deck", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="deck", cascade="all, delete-orphan")


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    front = Column(String, nullable=False)
    back = Column(String, nullable=False)
    image_url = Column(String, default="", nullable=False)
    position = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    deck = relationship("Deck", back_populates="cards")
    card_states = relationship("UserCardState", back_populates="card", cascade="all, delete-orphan")
    review_logs = relationship("ReviewLog", back_populates="card")


class UserSavedDeck(Base):
    __tablename__ = "user_saved_decks"
    __table_args__ = (UniqueConstraint("user_id", "deck_id", name="uq_user_saved_decks_user_deck"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    saved_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    user = relationship("User", back_populates="saved_deck_links")
    deck = relationship("Deck", back_populates="saved_by_links")


class UserCardState(Base):
    __tablename__ = "user_card_state"
    __table_args__ = (UniqueConstraint("user_id", "card_id", name="uq_user_card_state_user_card"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    status = Column(String, default="new", nullable=False)
    due_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    stability = Column(Float, default=0.4, nullable=False)
    difficulty = Column(Float, default=5.0, nullable=False)
    scheduled_days = Column(Float, default=0.0, nullable=False)
    elapsed_days = Column(Float, default=0.0, nullable=False)
    reps = Column(Integer, default=0, nullable=False)
    lapses = Column(Integer, default=0, nullable=False)
    learning_step = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    user = relationship("User", back_populates="card_states")
    deck = relationship("Deck", back_populates="card_states")
    card = relationship("Card", back_populates="card_states")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    session_id = Column(String, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    rating = Column(String, nullable=False)
    previous_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    previous_due_at = Column(DateTime(timezone=True), nullable=True)
    new_due_at = Column(DateTime(timezone=True), nullable=False)
    previous_stability = Column(Float, nullable=False)
    new_stability = Column(Float, nullable=False)
    previous_difficulty = Column(Float, nullable=False)
    new_difficulty = Column(Float, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    user = relationship("User", back_populates="review_logs")
    deck = relationship("Deck", back_populates="review_logs")
    card = relationship("Card", back_populates="review_logs")


class UserDeckProgress(Base):
    __tablename__ = "user_deck_progress"
    __table_args__ = (UniqueConstraint("user_id", "deck_id", name="uq_user_deck_progress_user_deck"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    total_cards = Column(Integer, default=0, nullable=False)
    # Keep legacy DB compatibility: old SQLite files use `new_count`/`due_count`.
    new_count = Column(Integer, default=0, nullable=False)
    new_available_count = synonym("new_count")
    learning_count = Column(Integer, default=0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)
    due_count = Column(Integer, default=0, nullable=False)
    due_review_count = synonym("due_count")
    known_count = Column(Integer, default=0, nullable=False)
    last_studied_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    user = relationship("User", back_populates="deck_progress")
    deck = relationship("Deck", back_populates="progress_rows")


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    mode = Column(String, nullable=False)
    shuffle_cards = Column(Boolean, default=False, nullable=False)
    card_order = Column(Text, default="[]", nullable=False)
    current_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="study_sessions")
    deck = relationship("Deck", back_populates="study_sessions")
