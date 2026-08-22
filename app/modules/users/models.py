import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel


class Role(str, PyEnum):
    TRAVELER = "traveler"
    HOST = "host"
    GUIDE = "guide"
    EXPERIENCE_PROVIDER = "experience_provider"
    SERVICE_PROVIDER = "service_provider"


class UserRole(BaseModel):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role_enum"), nullable=False, index=True
    )

    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    first_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        primaryjoin="User.id == UserRole.user_id",
        cascade="all, delete-orphan",
    )
    trips: Mapped[list["Trip"]] = relationship(
        "Trip",
        primaryjoin="User.id == Trip.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
