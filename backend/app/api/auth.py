import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import UserModel
from app.schemas.user import Token, UserCreate, UserRead, UserProfileUpdate, ChangePasswordRequest
from app.api.dependencies import get_current_user

router = APIRouter()


@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = db.query(UserModel).filter(UserModel.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    from datetime import datetime, timezone
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    access_token = security.create_access_token(user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserRead)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    Register a new user.
    """
    user = db.query(UserModel).filter(UserModel.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = UserModel(
        id=str(uuid.uuid4()),
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role=user_in.role or "technician",
        department=user_in.department,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def read_user_me(
    current_user: UserModel = Depends(get_current_user),
) -> Any:
    """
    Get current user.
    """
    return current_user


@router.patch("/me", response_model=UserRead)
def update_user_me(
    profile_in: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> Any:
    """
    Update current user's profile details.
    """
    if profile_in.first_name is not None:
        current_user.first_name = profile_in.first_name
    if profile_in.last_name is not None:
        current_user.last_name = profile_in.last_name
    if profile_in.department is not None:
        current_user.department = profile_in.department

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/change-password")
def change_user_password(
    password_in: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> Any:
    """
    Change current user's password after verifying existing password.
    """
    if not security.verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect.",
        )

    if len(password_in.new_password) < 4:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 4 characters long.",
        )

    current_user.hashed_password = security.get_password_hash(password_in.new_password)
    db.add(current_user)
    db.commit()
    return {"message": "Password updated successfully."}

