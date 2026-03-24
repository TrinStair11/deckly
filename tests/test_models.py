from backend.models import Card, Deck, ReviewLog, StudySession, User, UserCardState, UserDeckProgress, UserSavedDeck


def test_user_relationships_are_declared():
    assert User.decks.property.back_populates == "owner"
    assert User.saved_deck_links.property.back_populates == "user"
    assert User.card_states.property.back_populates == "user"


def test_deck_relationships_are_declared():
    assert Deck.owner.property.back_populates == "decks"
    assert Deck.cards.property.back_populates == "deck"
    assert Deck.saved_by_links.property.back_populates == "deck"
    assert Deck.progress_rows.property.back_populates == "deck"


def test_card_relationships_are_declared():
    assert Card.deck.property.back_populates == "cards"
    assert Card.card_states.property.back_populates == "card"
    assert Card.review_logs.property.back_populates == "card"


def test_user_card_state_relationships_are_declared():
    assert UserCardState.user.property.back_populates == "card_states"
    assert UserCardState.deck.property.back_populates == "card_states"
    assert UserCardState.card.property.back_populates == "card_states"


def test_review_log_and_progress_relationships_are_declared():
    assert ReviewLog.user.property.back_populates == "review_logs"
    assert ReviewLog.deck.property.back_populates == "review_logs"
    assert UserDeckProgress.user.property.back_populates == "deck_progress"
    assert UserSavedDeck.deck.property.back_populates == "saved_by_links"
    assert StudySession.user.property.back_populates == "study_sessions"


def test_deck_title_alias_uses_legacy_name_column():
    assert "name" in Deck.__table__.c
    deck = Deck(name="Japanese Core")
    assert deck.title == "Japanese Core"
    deck.title = "N5 Core"
    assert deck.name == "N5 Core"
