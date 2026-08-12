"""
Staff/admin accounts — anyone who logs into the system itself.
Not to be confused with Client, which is the business's own customers.
"""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"


class UserBase(SQLModel):
    email: str = Field(unique=True, index=True, max_length=255)
    role: UserRole = Field(default=UserRole.staff)
    is_active: bool = Field(default=True)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(UserBase):
    password: str  # plaintext in, hashed before storage — never stored as-is


class UserRead(UserBase):
    id: int
    created_at: datetime
