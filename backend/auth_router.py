from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from . import schemas
from .auth import get_db
from .runtime import LOGIN_RATE_LIMIT as DEFAULT_LOGIN_RATE_LIMIT
from .security_services import perform_login

router = APIRouter()

LOGIN_RATE_LIMIT = DEFAULT_LOGIN_RATE_LIMIT


@router.post("/login", response_model=schemas.Token)
def login_endpoint(
    payload: schemas.UserLogin,
    db: Session = Depends(get_db),
    response: Response = None,
    request: Request = None,
):
    return perform_login(payload, db, response=response, request=request, rate_limit=LOGIN_RATE_LIMIT)
