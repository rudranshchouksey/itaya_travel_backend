import enum
import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel as Base


class TripStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TripItemType(str, enum.Enum):
    STAY = "stay"
    EXPERIENCE = "experience"
    TRANSPORT = "transport"
    ACTIVITY = "activity"
    CUSTOM = "custom"


class TripParticipantRole(str, enum.Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class TripDestination(Base):
    __tablename__ = "trip_destinations"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("destinations.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    # Optional owner for guest trips
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    guest_token: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    traveler_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus), default=TripStatus.DRAFT, nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="check_trip_dates"),
        CheckConstraint("traveler_count > 0", name="check_traveler_count"),
    )

    owner = relationship("User", back_populates="trips")
    destinations = relationship(
        "Destination", secondary="trip_destinations", backref="trips"
    )
    days = relationship(
        "TripDay",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripDay.date",
    )
    items = relationship(
        "TripItem",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripItem.order_index",
    )
    participants = relationship(
        "TripParticipant", back_populates="trip", cascade="all, delete-orphan"
    )


class TripDay(Base):
    __tablename__ = "trip_days"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    trip = relationship("Trip", back_populates="days")
    items = relationship(
        "TripItem",
        back_populates="trip_day",
        cascade="all, delete-orphan",
        order_by="TripItem.order_index",
    )


class TripItem(Base):
    __tablename__ = "trip_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trip_day_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trip_days.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    item_type: Mapped[TripItemType] = mapped_column(Enum(TripItemType), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # External References
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    experience_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiences.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Scheduling
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(item_type = 'stay' AND listing_id IS NOT NULL) OR (item_type != 'stay')",
            name="check_stay_listing",
        ),
        CheckConstraint(
            "(item_type = 'experience' AND experience_id IS NOT NULL) OR (item_type != 'experience')",
            name="check_experience_ref",
        ),
    )

    trip = relationship("Trip", back_populates="items")
    trip_day = relationship("TripDay", back_populates="items")
    listing = relationship("Listing")
    experience = relationship("Experience")


class TripParticipant(Base):
    __tablename__ = "trip_participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    role: Mapped[TripParticipantRole] = mapped_column(
        Enum(TripParticipantRole), default=TripParticipantRole.VIEWER, nullable=False
    )

    trip = relationship("Trip", back_populates="participants")
    user = relationship("User")
