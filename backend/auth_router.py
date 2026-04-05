from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from . import schemas
from .auth import get_db
from .runtime import LOGIN_RATE_LIMIT as DEFAULT_LOGIN_RATE_LIMIT
from .security_services import perform_login

router = APIRouter(tags=["Auth"])

LOGIN_RATE_LIMIT = DEFAULT_LOGIN_RATE_LIMIT


@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Sign in",
    description="Authenticate a user and create a new session. Browser clients receive the auth cookie and API clients can reuse the returned token payload.",
    response_description="Authenticated session details and access token.",
)
def login_endpoint(
    payload: schemas.UserLogin,
    db: Session = Depends(get_db),
    response: Response = None,
    request: Request = None,
):
    return perform_login(payload, db, response=response, request=request, rate_limit=LOGIN_RATE_LIMIT)
