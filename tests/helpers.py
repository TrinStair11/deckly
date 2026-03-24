from uuid import uuid4

from backend import schemas
from backend.main import login, register


def make_email() -> str:
    return f"test-{uuid4().hex[:8]}@example.com"


def register_user(db_session, email=None, password="secret12"):
    return register(
        schemas.UserCreate(email=email or make_email(), password=password),
        db_session,
    )


def login_user(db_session, email, password="secret12"):
    return login(
        schemas.UserLogin(email=email, password=password),
        db_session,
    )
