from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, constr, validator


NonEmptyText = constr(strip_whitespace=True, min_length=1)
DeckTitle = constr(strip_whitespace=True, min_length=1, max_length=120)
DeckDescription = constr(strip_whitespace=True, max_length=500)
QuizTitle = constr(strip_whitespace=True, min_length=1, max_length=160)
QuizDescription = constr(strip_whitespace=True, max_length=1000)
QuizCategory = constr(strip_whitespace=True, max_length=120)
QuizLanguage = constr(strip_whitespace=True, max_length=120)
QuizCoverImage = constr(strip_whitespace=True, max_length=2000)
QuizQuestionText = constr(strip_whitespace=True, min_length=1, max_length=2000)
QuizExplanation = constr(strip_whitespace=True, max_length=2000)
QuizOptionText = constr(strip_whitespace=True, min_length=1, max_length=500)
ImageSearchQuery = constr(strip_whitespace=True, min_length=1, max_length=200)
ImageSourceUrl = constr(strip_whitespace=True, min_length=1, max_length=2000)
UploadFilename = constr(strip_whitespace=True, min_length=1, max_length=255)
VisibilityInput = constr(strip_whitespace=True, min_length=1, max_length=20)


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
    front: NonEmptyText
    back: NonEmptyText
    image_url: str = Field(default="")


class DeckCreate(BaseModel):
    title: DeckTitle = Field(alias="name")
    description: DeckDescription = ""
    cards: list[CardSeed] = Field(default_factory=list)
    visibility: VisibilityInput = "public"
    password: str = Field(default="", max_length=120, alias="access_password")

    class Config:
        allow_population_by_field_name = True

    @validator("visibility")
    def normalize_visibility(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"public", "private"}:
            raise ValueError("Visibility must be public or private")
        return normalized


class DeckUpdate(BaseModel):
    title: DeckTitle = Field(alias="name")
    description: DeckDescription = ""
    visibility: VisibilityInput = "public"
    password: str = Field(default="", max_length=120, alias="access_password")

    class Config:
        allow_population_by_field_name = True

    @validator("visibility")
    def normalize_visibility(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"public", "private"}:
            raise ValueError("Visibility must be public or private")
        return normalized


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
    is_owner: bool = False
    saved_in_library: bool = False
    saved_at: datetime | None = None
    progress: ProgressOut | None = None

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        fields = {"title": "name"}


class CardCreate(BaseModel):
    front: NonEmptyText
    back: NonEmptyText
    image_url: str = Field(default="")


class CardUpdate(BaseModel):
    front: NonEmptyText
    back: NonEmptyText
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
    ease_factor: float
    stability: float
    difficulty: float
    scheduled_days: float
    elapsed_days: float
    reps: int
    lapses: int
    learning_step: int

    class Config:
        orm_mode = True


class IntervalRatingPreview(BaseModel):
    again: str
    hard: str
    good: str
    easy: str


class CardOut(BaseModel):
    id: int
    front: str
    back: str
    image_url: str
    position: int
    deck_id: int
    state: UserCardStateOut | None = None
    interval_preview: IntervalRatingPreview | None = None

    class Config:
        orm_mode = True


class DeckDetail(DeckOut):
    cards: list[CardOut]


class DeckShareMeta(BaseModel):
    id: int
    title: str
    visibility: str
    requires_password: bool
    owner_id: int | None = None
    owner_name: str | None = None

    class Config:
        allow_population_by_field_name = True
        fields = {"title": "name"}


class SavedDeckOut(BaseModel):
    deck: DeckOut


class DeckAccessRequest(BaseModel):
    password: NonEmptyText = Field(max_length=120)


class DeckAccessToken(BaseModel):
    access_token: str
    token_type: str = "deck-access"


class CardReview(BaseModel):
    rating: Literal["again", "hard", "good", "easy"]


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
    rating: Literal["again", "hard", "good", "easy"]
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
    interval_preview: IntervalRatingPreview | None = None


class ImageSearchRequest(BaseModel):
    query: ImageSearchQuery
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
    source_url: ImageSourceUrl
    title: constr(strip_whitespace=True, max_length=500) = ""


class ImageUploadRequest(BaseModel):
    filename: UploadFilename
    content_base64: str = Field(min_length=1)


class StoredImageOut(BaseModel):
    image_url: str


class QuizOptionInput(BaseModel):
    id: int | None = None
    option_text: QuizOptionText
    is_correct: bool = False
    order_index: int | None = Field(default=None, ge=0)


class QuizQuestionInput(BaseModel):
    id: int | None = None
    question_text: QuizQuestionText
    question_type: Literal["single_choice", "multiple_choice"] = "single_choice"
    explanation: QuizExplanation = ""
    order_index: int | None = Field(default=None, ge=0)
    points: int = Field(default=1, ge=1, le=100)
    options: list[QuizOptionInput] = Field(default_factory=list)


class QuizCreate(BaseModel):
    title: QuizTitle
    description: QuizDescription = ""
    category: QuizCategory = ""
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    subject: QuizCategory = ""
    language: QuizLanguage = ""
    is_published: bool = False
    cover_image: QuizCoverImage = ""
    estimated_time: int | None = Field(default=None, ge=1, le=600)
    tags: list[str] = Field(default_factory=list)
    questions: list[QuizQuestionInput] = Field(default_factory=list)


class QuizUpdate(QuizCreate):
    pass


class QuizOptionOut(BaseModel):
    id: int
    option_text: str
    is_correct: bool
    order_index: int

    class Config:
        orm_mode = True


class QuizQuestionOut(BaseModel):
    id: int
    question_text: str
    question_type: str
    explanation: str
    order_index: int
    points: int
    options: list[QuizOptionOut]

    class Config:
        orm_mode = True


class QuizSummaryOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    difficulty: str
    subject: str
    language: str
    is_published: bool
    cover_image: str
    estimated_time: int | None = None
    tags: list[str] = Field(default_factory=list)
    question_count: int = 0
    total_points: int = 0
    attempt_count: int = 0
    owner_id: int
    owner_name: str
    can_edit: bool = False
    last_attempt_percentage: float | None = None
    best_attempt_percentage: float | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class QuizDetailOut(QuizSummaryOut):
    last_attempt_id: int | None = None


class QuizEditorOut(QuizDetailOut):
    questions: list[QuizQuestionOut] = Field(default_factory=list)


class QuizOptionChoiceOut(BaseModel):
    id: int
    option_text: str
    order_index: int


class QuizQuestionSessionOut(BaseModel):
    id: int
    question_text: str
    question_type: str
    order_index: int
    points: int
    options: list[QuizOptionChoiceOut]
    selected_option_id: int | None = None


class QuizAttemptSessionOut(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    status: str
    started_at: datetime
    total_questions: int
    answered_count: int
    current_question_index: int
    questions: list[QuizQuestionSessionOut]


class QuizAnswerSubmit(BaseModel):
    selected_option_id: int


class QuizResultSummaryOut(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    status: Literal["in_progress", "completed", "abandoned"]
    started_at: datetime
    finished_at: datetime | None = None
    score: float
    correct_count: int
    wrong_count: int
    total_questions: int
    percentage: float
    completion_time_seconds: int | None = None


class QuizReviewItemOut(BaseModel):
    question_id: int
    question_text: str
    selected_option_id: int | None = None
    selected_option_text: str | None = None
    correct_option_text: str
    explanation: str
    is_correct: bool
    order_index: int
    points: int


class QuizResultOut(QuizResultSummaryOut):
    review_items: list[QuizReviewItemOut] = Field(default_factory=list)


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
