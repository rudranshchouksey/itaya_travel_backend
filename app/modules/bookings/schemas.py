import uuid
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.bookings.models import BookingStatus, PaymentStatus
from app.modules.trips.models import TripItemType


class BookingGuestBase(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: str | None = Field(None, max_length=255)
    is_primary: bool = False


class BookingGuestCreate(BookingGuestBase):
    pass


class BookingGuestRead(BookingGuestBase):
    id: uuid.UUID
    booking_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class BookingItemBase(BaseModel):
    item_type: TripItemType
    listing_id: uuid.UUID | None = None
    experience_id: uuid.UUID | None = None

    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None

    quantity: int = Field(1, ge=1)
    guest_count: int = Field(1, ge=1)


class BookingItemCreate(BookingItemBase):
    @model_validator(mode="after")
    def validate_item(self) -> "BookingItemCreate":
        if self.item_type == TripItemType.STAY:
            assert self.listing_id is not None, "listing_id is required for stay bookings"
            assert self.start_date is not None, "start_date is required for stay bookings"
            assert self.end_date is not None, "end_date is required for stay bookings"
            assert self.start_date < self.end_date, "end_date must be after start_date"
        elif self.item_type == TripItemType.EXPERIENCE:
            assert self.experience_id is not None, "experience_id is required for experience bookings"
            assert self.start_date is not None, "start_date is required for experience bookings"
            assert self.start_time is not None, "start_time is required for experience bookings"
        else:
            raise ValueError(f"Booking not supported for item type: {self.item_type}")
        return self


class BookingItemRead(BookingItemBase):
    id: uuid.UUID
    booking_id: uuid.UUID
    price_snapshot: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    trip_id: uuid.UUID | None = None


class BookingCreate(BookingBase):
    currency: str = Field(..., max_length=3)
    items: list[BookingItemCreate] = Field(..., min_length=1)
    guests: list[BookingGuestCreate] = Field(..., min_length=1)
    
    @model_validator(mode="after")
    def validate_primary_guest(self) -> "BookingCreate":
        primary_guests = [g for g in self.guests if g.is_primary]
        assert len(primary_guests) == 1, "Exactly one primary guest is required"
        return self


class BookingRead(BookingBase):
    id: uuid.UUID
    user_id: uuid.UUID
    reference: str
    currency: str
    subtotal: Decimal
    fees: Decimal
    taxes: Decimal
    total: Decimal
    booking_status: BookingStatus
    payment_status: PaymentStatus
    
    items: list[BookingItemRead]
    guests: list[BookingGuestRead]

    model_config = ConfigDict(from_attributes=True)
