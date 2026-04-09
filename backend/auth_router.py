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
    summary="Вход",
    description="Авторизовать пользователя и создать новую сессию. Браузерные клиенты получают auth-cookie, а API-клиенты могут использовать возвращённый токен.",
    response_description="Данные авторизованной сессии и токен доступа.",
)
def login_endpoint(
    payload: schemas.UserLogin,
    db: Session = Depends(get_db),
    response: Response = None,
    request: Request = None,
):
    return perform_login(payload, db, response=response, request=request, rate_limit=LOGIN_RATE_LIMIT)
