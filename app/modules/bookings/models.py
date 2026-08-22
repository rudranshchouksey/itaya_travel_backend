import enum
import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.trips.models import TripItemType
from app.shared.models import BaseModel as Base


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    PAYMENT_PENDING = "payment_pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


BOOKING_STATUS_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {
        BookingStatus.PAYMENT_PENDING,
        BookingStatus.CONFIRMED,
        BookingStatus.COMPLETED,
        BookingStatus.CANCELLED,
    },
    BookingStatus.PAYMENT_PENDING: {
        BookingStatus.CONFIRMED,
        BookingStatus.FAILED,
        BookingStatus.CANCELLED,
    },
    BookingStatus.CONFIRMED: {
        BookingStatus.CANCELLED,
        BookingStatus.COMPLETED,
        BookingStatus.REFUNDED,
        BookingStatus.PARTIALLY_REFUNDED,
    },
    BookingStatus.CANCELLED: {
        BookingStatus.REFUNDED,
        BookingStatus.PARTIALLY_REFUNDED,
    },
    BookingStatus.COMPLETED: {
        BookingStatus.REFUNDED,
        BookingStatus.PARTIALLY_REFUNDED,
    },
    BookingStatus.FAILED: set(),
    BookingStatus.REFUNDED: set(),
    BookingStatus.PARTIALLY_REFUNDED: {BookingStatus.REFUNDED},
}


def validate_booking_transition(current: BookingStatus, target: BookingStatus) -> bool:
    return target in BOOKING_STATUS_TRANSITIONS.get(current, set())


class Booking(Base):
    __tablename__ = "bookings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )

    reference: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    platform_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    provider_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    taxes: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    discounts: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    booking_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status_enum", create_type=False),
        default=BookingStatus.PENDING,
        nullable=False,
        index=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    trip = relationship("Trip", back_populates="bookings")
    payments = relationship(
        "Payment",
        back_populates="booking",
        cascade="all, delete-orphan",
    )

    items: Mapped[list["BookingItem"]] = relationship(
        "BookingItem",
        primaryjoin="Booking.id == BookingItem.booking_id",
        cascade="all, delete-orphan",
        back_populates="booking",
    )
    guests: Mapped[list["BookingGuest"]] = relationship(
        "BookingGuest",
        primaryjoin="Booking.id == BookingGuest.booking_id",
        cascade="all, delete-orphan",
        back_populates="booking",
    )


class BookingItem(Base):
    __tablename__ = "booking_items"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[TripItemType] = mapped_column(
        Enum(TripItemType, name="trip_item_type_enum", create_type=False),
        nullable=False,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listings.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    experience_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiences.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    taxes: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    fees: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    __table_args__ = (
        CheckConstraint(
            "(item_type = 'STAY' AND listing_id IS NOT NULL AND start_date IS NOT NULL AND end_date IS NOT NULL) OR "
            "(item_type = 'EXPERIENCE' AND experience_id IS NOT NULL AND start_date IS NOT NULL AND start_time IS NOT NULL) OR "
            "(item_type = 'stay' AND listing_id IS NOT NULL AND start_date IS NOT NULL AND end_date IS NOT NULL) OR "
            "(item_type = 'experience' AND experience_id IS NOT NULL AND start_date IS NOT NULL AND start_time IS NOT NULL)",
            name="check_booking_item_references",
        ),
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="items",
    )
    listing = relationship("Listing")
    experience = relationship("Experience")
    review = relationship("Review", back_populates="booking_item", uselist=False)


class BookingGuest(Base):
    __tablename__ = "booking_guests"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="guests",
    )
