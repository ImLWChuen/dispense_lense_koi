from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserModel(Base):
    """Represents a user in the system."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
