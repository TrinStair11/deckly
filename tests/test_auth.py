import pytest
from fastapi import HTTPException
from jose import jwt

from backend.auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_current_user,
    get_db,
    hash_password,
    verify_password,
)

from tests.helpers import login_user, make_email, register_user


def test_login_returns_bearer_token_with_string_subject(db_session):
    email = make_email()
    user = register_user(db_session, email=email)

    payload = login_user(db_session, email)
    decoded = jwt.decode(payload["access_token"], SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["token_type"] == "bearer"
    assert decoded["sub"] == str(user.id)


def test_login_rejects_invalid_credentials(db_session):
    email = make_email()
    register_user(db_session, email=email)

    with pytest.raises(HTTPException) as exc_info:
        login_user(db_session, email=email, password="wrongpass")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid credentials"


def test_get_current_user_returns_matching_user(db_session):
    email = make_email()
    user = register_user(db_session, email=email)
    token = create_access_token({"sub": user.id})

    current_user = get_current_user(token=token, db=db_session)

    assert current_user.id == user.id


def test_get_current_user_rejects_invalid_signature(db_session):
    token = create_access_token({"sub": "1"}) + "broken"

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"


def test_get_current_user_rejects_token_without_subject(db_session):
    token = create_access_token({"scope": "missing-sub"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_non_numeric_subject(db_session):
    token = create_access_token({"sub": "not-a-number"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_missing_user(db_session):
    token = create_access_token({"sub": "999999"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db_session)

    assert exc_info.value.status_code == 401


def test_password_hashing_and_verification_helpers():
    password = "secret12"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrongpass", password_hash) is False


def test_get_db_closes_session(monkeypatch):
    closed = {"value": False}

    class FakeSession:
        def close(self):
            closed["value"] = True

    monkeypatch.setattr("backend.auth.SessionLocal", lambda: FakeSession())

    dependency = get_db()
    session = next(dependency)

    assert isinstance(session, FakeSession)
    with pytest.raises(StopIteration):
        next(dependency)
    assert closed["value"] is True
