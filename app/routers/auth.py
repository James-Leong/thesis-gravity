from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ROLE_VALUES
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.auth import UserCreate, UserLogin, UserProfileUpdate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if payload.role not in ROLE_VALUES:
        raise HTTPException(status_code=400, detail="Invalid role.")
    if payload.role in ("admin", "academic"):
        raise HTTPException(status_code=403, detail="Cannot register with this role.")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserRead)
def login_user(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(str(user.id))
    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/profile", response_model=UserRead)
def update_profile(
    payload: UserProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.name is not None:
        current_user.name = payload.name.strip() or None
    db.commit()
    db.refresh(current_user)
    return current_user
