from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user, get_db
from .decks import get_next_card_position, get_owned_card_or_404, get_owned_deck_or_404
from .spaced_repetition import get_active_cards, serialize_card, utcnow

router = APIRouter(tags=["Cards"])


@router.post(
    "/decks/{deck_id}/cards",
    response_model=schemas.CardOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать карточку",
    description="Добавить новую карточку в колоду, принадлежащую авторизованному пользователю.",
    response_description="Созданная карточка.",
)
def create_card(deck_id: int, card: schemas.CardCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    now = utcnow()
    new_card = models.Card(
        front=card.front.strip(),
        back=card.back.strip(),
        image_url=card.image_url.strip(),
        position=get_next_card_position(deck.id, db),
        deck_id=deck.id,
        created_at=now,
        updated_at=now,
    )
    deck.updated_at = now
    db.add(new_card)
    db.commit()
    db.refresh(new_card)
    return serialize_card(new_card)


@router.put(
    "/cards/{card_id}",
    response_model=schemas.CardOut,
    summary="Обновить карточку",
    description="Обновить содержимое и ссылку на изображение для карточки, принадлежащей авторизованному пользователю.",
    response_description="Обновлённая карточка.",
)
def update_card(card_id: int, payload: schemas.CardUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    card = get_owned_card_or_404(card_id, current_user.id, db)
    card.front = payload.front.strip()
    card.back = payload.back.strip()
    card.image_url = payload.image_url.strip()
    card.updated_at = utcnow()
    card.deck.updated_at = card.updated_at
    db.commit()
    db.refresh(card)
    return serialize_card(card)


@router.delete(
    "/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить карточку",
    description="Мягко удалить карточку из колоды, принадлежащей авторизованному пользователю.",
    response_description="Карточка успешно удалена.",
)
def delete_card(card_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    card = get_owned_card_or_404(card_id, current_user.id, db)
    now = utcnow()
    card.deleted_at = now
    card.updated_at = now
    card.deck.updated_at = now
    db.commit()


@router.put(
    "/decks/{deck_id}/cards/reorder",
    response_model=list[schemas.CardOut],
    summary="Изменить порядок карточек",
    description="Заменить порядок всех активных карточек в колоде. В запросе каждая активная карточка должна быть указана ровно один раз.",
    response_description="Карточки в обновлённом порядке.",
)
def reorder_cards(deck_id: int, payload: schemas.CardReorder, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    cards_by_id = {card.id: card for card in get_active_cards(deck)}
    if {item.id for item in payload.items} != set(cards_by_id):
        raise HTTPException(status_code=400, detail="Запрос на перестановку должен содержать все карточки колоды")
    if len({item.position for item in payload.items}) != len(payload.items):
        raise HTTPException(status_code=400, detail="В запросе на перестановку позиции должны быть уникальными")
    for item in payload.items:
        cards_by_id[item.id].position = item.position
        cards_by_id[item.id].updated_at = utcnow()
    deck.updated_at = utcnow()
    db.commit()
    return [serialize_card(card) for card in sorted(cards_by_id.values(), key=lambda item: item.position)]


@router.get(
    "/cards",
    response_model=list[schemas.CardOut],
    summary="Список карточек",
    description="Вернуть все активные карточки авторизованного пользователя во всех колодах.",
    response_description="Список активных карточек.",
)
def list_cards(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    cards = (
        db.query(models.Card)
        .join(models.Deck, models.Card.deck_id == models.Deck.id)
        .filter(models.Deck.owner_id == current_user.id, models.Card.deleted_at.is_(None))
        .order_by(models.Card.position)
        .all()
    )
    return [serialize_card(card) for card in cards]
