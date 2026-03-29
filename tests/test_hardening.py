import httpx
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import backend.main as main_module
from backend import models, schemas
from backend.auth import get_current_user
from backend.main import (
    access_private_deck,
    create_deck,
    download_external_image,
    ensure_redirect_allowed,
    get_shared_deck_meta,
    guess_image_extension,
    login,
    normalize_openverse_results,
    logout,
    reorder_cards,
    register,
    save_shared_deck,
    search_openverse_images,
    validate_external_image_url,
)
from backend.spaced_repetition import advance_session, build_study_session, refresh_user_deck_progress
from tests.helpers import make_email, register_user


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00"
)


def test_http_login_uses_cookie_auth_and_logout_clears_it(db_session):
    email = make_email().upper()
    response = Response()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    register_response = register(schemas.UserCreate(email=email, password="secret12"), db_session)
    login_response = login(schemas.UserLogin(email=email, password="secret12"), db_session, response=response, request=request)
    current_user = get_current_user(access_token=login_response["access_token"], db=db_session)
    logout_response = Response()
    logout(logout_response)

    assert register_response.email == email.lower()
    assert login_response["token_type"] == "bearer"
    assert "access_token=" in response.headers["set-cookie"]
    assert current_user.email == email.lower()
    assert "Max-Age=0" in logout_response.headers["set-cookie"]


def test_login_rate_limit_returns_429_after_repeated_failures(db_session, monkeypatch):
    email = make_email()
    register(schemas.UserCreate(email=email, password="secret12"), db_session)
    monkeypatch.setattr(main_module, "LOGIN_RATE_LIMIT", 2)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    with pytest.raises(HTTPException) as first:
        login(schemas.UserLogin(email=email, password="bad-pass"), db_session, request=request)
    with pytest.raises(HTTPException) as second:
        login(schemas.UserLogin(email=email, password="bad-pass"), db_session, request=request)
    with pytest.raises(HTTPException) as third:
        login(schemas.UserLogin(email=email, password="bad-pass"), db_session, request=request)

    assert first.value.status_code == 401
    assert second.value.status_code == 401
    assert third.value.status_code == 429


def test_private_deck_access_rate_limit_returns_429(db_session, monkeypatch):
    owner = register_user(db_session, email=make_email())
    deck = create_deck(
        schemas.DeckCreate(name="Secret", description="Deck", visibility="private", access_password="abcd1234"),
        current_user=owner,
        db=db_session,
    )
    monkeypatch.setattr(main_module, "DECK_ACCESS_RATE_LIMIT", 2)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    with pytest.raises(HTTPException) as first:
        access_private_deck(deck.id, schemas.DeckAccessRequest(password="wrong"), db=db_session, request=request)
    with pytest.raises(HTTPException) as second:
        access_private_deck(deck.id, schemas.DeckAccessRequest(password="wrong"), db=db_session, request=request)
    with pytest.raises(HTTPException) as third:
        access_private_deck(deck.id, schemas.DeckAccessRequest(password="wrong"), db=db_session, request=request)

    assert first.value.status_code == 401
    assert second.value.status_code == 401
    assert third.value.status_code == 429


def test_save_shared_deck_returns_200_when_link_already_exists(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    deck = create_deck(
        schemas.DeckCreate(name="Shared", description="Deck"),
        current_user=owner,
        db=db_session,
    )
    first_response = Response(status_code=201)
    second_response = Response(status_code=201)

    save_shared_deck(deck.id, current_user=learner, db=db_session, response=first_response)
    save_shared_deck(deck.id, current_user=learner, db=db_session, response=second_response)

    assert first_response.status_code == 201
    assert second_response.status_code == 200


def test_private_share_meta_reveals_owner_with_valid_access_token(db_session):
    owner = register_user(db_session, email=make_email())
    deck = create_deck(
        schemas.DeckCreate(name="Meta", description="Deck", visibility="private", access_password="abcd1234"),
        current_user=owner,
        db=db_session,
    )

    token = access_private_deck(deck.id, schemas.DeckAccessRequest(password="abcd1234"), db=db_session)
    meta = get_shared_deck_meta(deck.id, db_session, x_deck_access_token=token["access_token"])

    assert meta.owner_name == owner.email.split("@")[0]


def test_validate_external_image_url_allows_public_https_and_redirect(monkeypatch):
    monkeypatch.setattr(
        main_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    validated = validate_external_image_url("https://example.com/image.png")
    redirected = ensure_redirect_allowed("https://example.com/image.png", "/next.png")

    assert validated == "https://example.com/image.png"
    assert redirected == "https://example.com/next.png"


def test_validate_external_image_url_rejects_non_https_and_private_hosts(monkeypatch):
    with pytest.raises(HTTPException, match="Only https image URLs are allowed"):
        validate_external_image_url("http://example.com/image.png")

    monkeypatch.setattr(
        main_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )

    with pytest.raises(HTTPException, match="Image host is not allowed"):
        validate_external_image_url("https://localhost/image.png")


def test_guess_image_extension_prefers_content_type_then_filename():
    assert guess_image_extension("image/webp", "fallback.jpg") == ".webp"
    assert guess_image_extension(None, "fallback.gif") == ".gif"
    assert guess_image_extension("application/octet-stream", "unknown.bin") == ".jpg"


def test_normalize_openverse_results_skips_items_without_urls():
    results = normalize_openverse_results(
        {
            "results": [
                {"id": "img-1", "title": "Bus", "thumbnail": "https://example.com/thumb.jpg", "url": "https://example.com/full.jpg"},
                {"id": "img-2", "title": "Skip", "thumbnail": None, "url": "https://example.com/skip.jpg"},
            ]
        }
    )

    assert len(results) == 1
    assert results[0].external_id == "img-1"


def test_search_openverse_images_normalizes_provider_payload(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {"id": "img-1", "title": "Bus", "thumbnail": "https://example.com/thumb.jpg", "url": "https://example.com/full.jpg"},
                    {"id": "img-2", "title": "Skip", "thumbnail": "https://example.com/thumb-2.jpg"},
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(main_module.httpx, "Client", FakeClient)

    results = search_openverse_images("bus", 1, 10)

    assert len(results) == 1
    assert results[0].title == "Bus"


def test_search_openverse_images_returns_502_when_provider_fails(monkeypatch):
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(main_module.httpx, "Client", BrokenClient)

    with pytest.raises(HTTPException, match="Image search provider is unavailable"):
        search_openverse_images("bus", 1, 10)


def test_download_external_image_follows_safe_redirect_and_stores_content(monkeypatch):
    stored = {}

    class FakeStreamResponse:
        def __init__(self, status_code, headers, chunks=None):
            self.status_code = status_code
            self.headers = headers
            self._chunks = chunks or []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield from self._chunks

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.responses = [
                FakeStreamResponse(302, {"location": "/final.png"}),
                FakeStreamResponse(
                    200,
                    {"content-type": "image/png", "content-length": str(len(PNG_BYTES))},
                    [PNG_BYTES],
                ),
            ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return self.responses.pop(0)

    monkeypatch.setattr(
        main_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    monkeypatch.setattr(main_module.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        main_module,
        "store_image_bytes",
        lambda content, extension: stored.update({"content": content, "extension": extension}) or "/media/final.png",
    )

    image_url = download_external_image("https://example.com/original.png")

    assert image_url == "/media/final.png"
    assert stored["content"] == PNG_BYTES
    assert stored["extension"] == ".png"


def test_download_external_image_rejects_non_image_content(monkeypatch):
    class FakeStreamResponse:
        status_code = 200
        headers = {"content-type": "text/plain", "content-length": "4"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"text"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return FakeStreamResponse()

    monkeypatch.setattr(
        main_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    monkeypatch.setattr(main_module.httpx, "Client", FakeClient)

    with pytest.raises(HTTPException, match="The selected file is not an image"):
        download_external_image("https://example.com/file.txt")


def test_reorder_cards_rejects_duplicate_positions(db_session):
    owner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(
            name="Reorder",
            description="Deck",
            cards=[schemas.CardSeed(front="One", back="1"), schemas.CardSeed(front="Two", back="2")],
        ),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()

    with pytest.raises(HTTPException, match="unique positions"):
        reorder_cards(
            deck.id,
            schemas.CardReorder(
                items=[
                    schemas.CardReorderItem(id=deck.cards[0].id, position=0),
                    schemas.CardReorderItem(id=deck.cards[1].id, position=0),
                ]
            ),
            current_user=owner,
            db=db_session,
        )


def test_refresh_user_deck_progress_persist_false_does_not_create_row(db_session):
    owner = register_user(db_session, email=make_email())
    deck = models.Deck(
        name="Progress",
        description="Deck",
        visibility="public",
        owner_id=owner.id,
    )
    db_session.add(deck)
    db_session.commit()
    db_session.refresh(deck)

    progress = refresh_user_deck_progress(deck, owner.id, db_session, persist=False)
    persisted = (
        db_session.query(models.UserDeckProgress)
        .filter(models.UserDeckProgress.deck_id == deck.id, models.UserDeckProgress.user_id == owner.id)
        .first()
    )

    assert progress.total_cards == 0
    assert persisted is None


def test_build_study_session_rejects_invalid_arguments(db_session):
    owner = register_user(db_session, email=make_email())
    deck = db_session.query(models.Deck).filter(
        models.Deck.id
        == create_deck(
            schemas.DeckCreate(name="Study", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
            current_user=owner,
            db=db_session,
        ).id
    ).first()

    with pytest.raises(HTTPException, match="Unsupported study mode"):
        build_study_session(deck, owner, db_session, mode="broken")
    with pytest.raises(HTTPException, match="limit must be at least 1"):
        build_study_session(deck, owner, db_session, mode="limited", limit=0)
    with pytest.raises(HTTPException, match="cannot be negative"):
        build_study_session(deck, owner, db_session, mode="interval", new_cards_limit=-1)


def test_advance_session_rejects_wrong_card_for_current_order(db_session):
    owner = register_user(db_session, email=make_email())
    deck = db_session.query(models.Deck).filter(
        models.Deck.id
        == create_deck(
            schemas.DeckCreate(
                name="Session",
                description="Deck",
                cards=[schemas.CardSeed(front="One", back="1"), schemas.CardSeed(front="Two", back="2")],
            ),
            current_user=owner,
            db=db_session,
        ).id
    ).first()

    session = build_study_session(deck, owner, db_session, mode="interval")
    wrong_card_id = session.card_order[1]

    with pytest.raises(HTTPException, match="current session order"):
        advance_session(session.session_id, wrong_card_id, owner.id, deck.id, db_session)
