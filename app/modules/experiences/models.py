import uuid
from datetime import date, time
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel


class ExperienceStatus(str, PyEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNLISTED = "unlisted"


class ExperienceVerificationStatus(str, PyEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ExperienceCategory(BaseModel):
    __tablename__ = "experience_categories"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ExperienceCategoryLink(BaseModel):
    __tablename__ = "experience_category_links"

    experience_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experience_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("experience_id", "category_id", name="uq_experience_category"),
    )


class ExperienceImage(BaseModel):
    __tablename__ = "experience_images"

    experience_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ExperienceAvailability(BaseModel):
    __tablename__ = "experience_availabilities"

    experience_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    price_override: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "experience_id", "date", "start_time", name="uq_experience_date_time"
        ),
    )


class Experience(BaseModel):
    __tablename__ = "experiences"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    guest_capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    meeting_point: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[ExperienceStatus] = mapped_column(
        Enum(ExperienceStatus, name="experience_status_enum"),
        default=ExperienceStatus.DRAFT,
        nullable=False,
        index=True,
    )
    verification_status: Mapped[ExperienceVerificationStatus] = mapped_column(
        Enum(ExperienceVerificationStatus, name="experience_verification_status_enum"),
        default=ExperienceVerificationStatus.PENDING,
        nullable=False,
    )

    # Relationships
    images: Mapped[list[ExperienceImage]] = relationship(
        "ExperienceImage",
        primaryjoin="Experience.id == ExperienceImage.experience_id",
        cascade="all, delete-orphan",
        order_by="ExperienceImage.display_order",
    )

    categories: Mapped[list[ExperienceCategory]] = relationship(
        "ExperienceCategory",
        secondary="experience_category_links",
        primaryjoin="Experience.id == ExperienceCategoryLink.experience_id",
        secondaryjoin="ExperienceCategory.id == ExperienceCategoryLink.category_id",
        viewonly=True,
    )

    reviews = relationship(
        "Review",
        primaryjoin="Experience.id == Review.experience_id",
        cascade="all, delete-orphan",
        back_populates="experience",
    )
