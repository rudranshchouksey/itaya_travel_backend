import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel as Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("booking_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    experience_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), nullable=True, index=True
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Store images as JSON array
    images: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    __table_args__ = (
        UniqueConstraint("user_id", "booking_item_id", name="uq_user_booking_item_review"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_valid_rating"),
        CheckConstraint(
            "(listing_id IS NOT NULL AND experience_id IS NULL) OR (listing_id IS NULL AND experience_id IS NOT NULL)",
            name="check_review_target_exclusive",
        ),
    )

    # Relationships
    user = relationship("User")
    booking_item = relationship("BookingItem", back_populates="review")
    listing = relationship("Listing", back_populates="reviews")
    experience = relationship("Experience", back_populates="reviews")
