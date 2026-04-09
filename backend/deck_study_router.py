from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from . import schemas
from .auth import get_current_user, get_db
from .decks import get_accessible_deck_or_404
from .spaced_repetition import build_study_session, refresh_user_deck_progress

router = APIRouter(tags=["Study"])


@router.get(
    "/decks/{deck_id}/study/session",
    response_model=schemas.StudySession,
    summary="Собрать учебную сессию",
    description="Сгенерировать учебную сессию для колоды с учётом выбранного режима, лимитов карточек и параметров перемешивания. Для приватных общих колод может потребоваться `X-Deck-Access-Token`.",
    response_description="Подготовленные данные учебной сессии.",
)
def get_study_session(
    deck_id: int,
    mode: str = "interval",
    limit: Annotated[int | None, Query(ge=1)] = None,
    new_cards_limit: Annotated[int, Query(ge=0, le=200)] = 10,
    shuffle_cards: bool = False,
    restart_session: bool = False,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return build_study_session(
        deck,
        current_user,
        db,
        mode=mode,
        limit=limit,
        new_cards_limit=new_cards_limit,
        shuffle_cards=shuffle_cards,
        persist_progress=False,
        restart_session=restart_session,
    )


@router.get(
    "/decks/{deck_id}/study",
    response_model=schemas.StudySession,
    summary="Получить устаревшую сессию изучения",
    description="Устаревший маршрут учебной сессии оставлен для обратной совместимости. Для новых интеграций используйте `/decks/{deck_id}/study/session`.",
    response_description="Подготовленные данные учебной сессии.",
    deprecated=True,
)
def get_legacy_study_session(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return build_study_session(deck, current_user, db, mode="interval", persist_progress=False)


@router.get(
    "/decks/{deck_id}/progress",
    response_model=schemas.ProgressOut,
    summary="Получить прогресс по колоде",
    description="Вернуть прогресс интервального повторения текущего пользователя по указанной колоде. Для приватных общих колод может потребоваться `X-Deck-Access-Token`.",
    response_description="Снимок прогресса пользователя по колоде.",
)
def get_deck_progress(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return refresh_user_deck_progress(deck, current_user.id, db, persist=False)
