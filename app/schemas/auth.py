from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import ROLE_STUDENT


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = ROLE_STUDENT
    name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    name: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
