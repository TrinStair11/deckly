from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import (
    clear_auth_cookie,
    get_current_user,
    get_db,
    hash_password,
    verify_password,
)

router = APIRouter(tags=["Account"])


@router.post(
    "/register",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация аккаунта",
    description="Создать новый пользовательский аккаунт с уникальным email и хешированным паролем.",
    response_description="Созданный пользовательский аккаунт.",
)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()
    existing = db.query(models.User).filter(models.User.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    user = models.User(email=normalized_email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/logout",
    response_model=schemas.AccountActionResult,
    summary="Выход из аккаунта",
    description="Очистить активную auth-cookie для текущей браузерной сессии.",
    response_description="Подтверждение выхода.",
)
def logout(response: Response):
    clear_auth_cookie(response)
    return schemas.AccountActionResult(message="Выход выполнен")


@router.get(
    "/me",
    response_model=schemas.UserOut,
    summary="Текущий аккаунт",
    description="Вернуть профиль текущего авторизованного пользователя.",
    response_description="Текущий авторизованный пользователь.",
)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.put(
    "/account/email",
    response_model=schemas.UserOut,
    summary="Обновить email аккаунта",
    description="Изменить email авторизованного пользователя после проверки текущего пароля и подтверждения email.",
    response_description="Обновлённый профиль пользователя.",
)
def update_account_email(
    payload: schemas.AccountEmailUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Текущий пароль неверный")
    if payload.new_email != payload.confirm_email:
        raise HTTPException(status_code=400, detail="Подтверждение email не совпадает")

    target_email = payload.new_email.strip().lower()
    if target_email == current_user.email:
        raise HTTPException(status_code=400, detail="Новый email должен отличаться от текущего")

    existing = (
        db.query(models.User)
        .filter(models.User.email == target_email, models.User.id != current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Этот email уже используется")

    current_user.email = target_email
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put(
    "/account/password",
    response_model=schemas.AccountActionResult,
    summary="Обновить пароль аккаунта",
    description="Изменить пароль авторизованного пользователя после проверки текущего пароля и полей подтверждения.",
    response_description="Подтверждение обновления пароля.",
)
def update_account_password(
    payload: schemas.AccountPasswordUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Текущий пароль неверный")
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="Подтверждение пароля не совпадает")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="Новый пароль должен отличаться от текущего")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return schemas.AccountActionResult(message="Пароль обновлён")
