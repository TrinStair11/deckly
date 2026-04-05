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
    summary="Register account",
    description="Create a new user account with a unique email address and a hashed password.",
    response_description="Newly created user account.",
)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()
    existing = db.query(models.User).filter(models.User.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    user = models.User(email=normalized_email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/logout",
    response_model=schemas.AccountActionResult,
    summary="Sign out",
    description="Clear the active authentication cookie for the current browser session.",
    response_description="Logout confirmation.",
)
def logout(response: Response):
    clear_auth_cookie(response)
    return schemas.AccountActionResult(message="Logged out successfully")


@router.get(
    "/me",
    response_model=schemas.UserOut,
    summary="Get current account",
    description="Return the authenticated user's profile.",
    response_description="Current authenticated user.",
)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.put(
    "/account/email",
    response_model=schemas.UserOut,
    summary="Update account email",
    description="Change the authenticated user's email address after validating the current password and email confirmation.",
    response_description="Updated user profile.",
)
def update_account_email(
    payload: schemas.AccountEmailUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.new_email != payload.confirm_email:
        raise HTTPException(status_code=400, detail="Email confirmation does not match")

    target_email = payload.new_email.strip().lower()
    if target_email == current_user.email:
        raise HTTPException(status_code=400, detail="New email must be different from current email")

    existing = (
        db.query(models.User)
        .filter(models.User.email == target_email, models.User.id != current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email is already in use")

    current_user.email = target_email
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put(
    "/account/password",
    response_model=schemas.AccountActionResult,
    summary="Update account password",
    description="Change the authenticated user's password after validating the current password and confirmation fields.",
    response_description="Password update confirmation.",
)
def update_account_password(
    payload: schemas.AccountPasswordUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return schemas.AccountActionResult(message="Password updated successfully")
