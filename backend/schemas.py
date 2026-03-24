from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CardSeed(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    image_url: str = Field(default="")


class DeckCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120, alias="name")
    description: str = Field(default="", max_length=500)
    cards: list[CardSeed] = Field(default_factory=list)
    visibility: str = Field(default="public", pattern="^(public|private)$")
    password: str = Field(default="", max_length=120, alias="access_password")

    class Config:
        allow_population_by_field_name = True


class DeckUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120, alias="name")
    description: str = Field(default="", max_length=500)
    visibility: str = Field(default="public", pattern="^(public|private)$")
    password: str = Field(default="", max_length=120, alias="access_password")

    class Config:
        allow_population_by_field_name = True


class ProgressOut(BaseModel):
    total_cards: int
    new_available_count: int
    learning_count: int
    review_count: int
    due_review_count: int
    known_count: int
    last_studied_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        orm_mode = True


class DeckOut(BaseModel):
    id: int
    title: str
    description: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    card_count: int = 0
    owner_id: int
    owner_name: str
    owner_email: EmailStr
    is_owner: bool = False
    saved_in_library: bool = False
    saved_at: datetime | None = None
    progress: ProgressOut | None = None

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        fields = {"title": "name"}


class CardCreate(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    image_url: str = Field(default="")


class CardUpdate(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    image_url: str = Field(default="")


class CardReorderItem(BaseModel):
    id: int
    position: int = Field(ge=0)


class CardReorder(BaseModel):
    items: list[CardReorderItem] = Field(default_factory=list)


class UserCardStateOut(BaseModel):
    status: Literal["new", "learning", "review", "relearning"]
    due_at: datetime
    last_reviewed_at: datetime | None = None
    stability: float
    difficulty: float
    scheduled_days: float
    elapsed_days: float
    reps: int
    lapses: int
    learning_step: int

    class Config:
        orm_mode = True


class CardOut(BaseModel):
    id: int
    front: str
    back: str
    image_url: str
    position: int
    deck_id: int
    state: UserCardStateOut | None = None

    class Config:
        orm_mode = True


class DeckDetail(DeckOut):
    cards: list[CardOut]


class DeckShareMeta(BaseModel):
    id: int
    title: str
    visibility: str
    requires_password: bool
    owner_id: int
    owner_name: str
    owner_email: EmailStr

    class Config:
        allow_population_by_field_name = True
        fields = {"title": "name"}


class SavedDeckOut(BaseModel):
    deck: DeckOut


class DeckAccessRequest(BaseModel):
    password: str = Field(min_length=1, max_length=120)


class DeckAccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CardReview(BaseModel):
    rating: Literal["again", "hard", "good", "easy", "perfect"]


class StudySession(BaseModel):
    session_id: str
    deck_id: int
    deck_title: str = Field(alias="deck_name")
    mode: Literal["review_all", "limited", "interval"]
    current_index: int = 0
    card_order: list[int] = Field(default_factory=list)
    total_cards: int
    cards: list[CardOut]
    progress: ProgressOut

    class Config:
        allow_population_by_field_name = True


class ReviewSubmit(BaseModel):
    deck_id: int
    card_id: int
    rating: Literal["again", "hard", "good", "easy", "perfect"]
    session_id: str
    response_time_ms: int | None = Field(default=None, ge=0)


class ReviewResult(BaseModel):
    card_id: int
    deck_id: int
    rating: str
    session_id: str
    session_current_index: int | None = None
    state: UserCardStateOut
    progress: ProgressOut
    next_due_at: datetime


class ImageSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=30)


class ImageSearchResult(BaseModel):
    provider: str
    external_id: str
    title: str
    thumbnail_url: str
    source_url: str
    author: str | None = None
    license: str | None = None


class ImageSearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    results: list[ImageSearchResult]


class ImageImportRequest(BaseModel):
    source_url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=500)


class ImageUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)


class StoredImageOut(BaseModel):
    image_url: str


class AccountEmailUpdate(BaseModel):
    new_email: EmailStr
    confirm_email: EmailStr
    current_password: str = Field(min_length=1, max_length=120)


class AccountPasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=120)
    new_password: str = Field(min_length=6, max_length=120)
    confirm_new_password: str = Field(min_length=6, max_length=120)


class AccountActionResult(BaseModel):
    message: str
