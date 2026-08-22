import uuid
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.trips.models import TripItemType, TripStatus


class TripItemBase(BaseModel):
    trip_day_id: uuid.UUID | None = None
    item_type: TripItemType
    title: str = Field(..., max_length=200)
    notes: str | None = None
    listing_id: uuid.UUID | None = None
    experience_id: uuid.UUID | None = None
    start_time: time | None = None
    end_time: time | None = None
    estimated_cost: Decimal | None = None
    order_index: int = 0

    @model_validator(mode="after")
    def validate_references(self) -> "TripItemBase":
        if self.item_type == TripItemType.STAY:
            assert self.listing_id is not None, "Stay items must have a listing_id"
        if self.item_type == TripItemType.EXPERIENCE:
            assert self.experience_id is not None, (
                "Experience items must have an experience_id"
            )
        if self.item_type != TripItemType.STAY:
            assert self.listing_id is None, "Only stay items can have a listing_id"
        if self.item_type != TripItemType.EXPERIENCE:
            assert self.experience_id is None, (
                "Only experience items can have an experience_id"
            )
        return self


class TripItemCreate(TripItemBase):
    pass


class TripItemUpdate(BaseModel):
    trip_day_id: uuid.UUID | None = None
    title: str | None = Field(None, max_length=200)
    notes: str | None = None
    listing_id: uuid.UUID | None = None
    experience_id: uuid.UUID | None = None
    start_time: time | None = None
    end_time: time | None = None
    estimated_cost: Decimal | None = None
    order_index: int | None = None


class TripItemRead(TripItemBase):
    id: uuid.UUID
    trip_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class TripDayBase(BaseModel):
    date: date
    title: str | None = Field(None, max_length=100)
    notes: str | None = None


class TripDayCreate(TripDayBase):
    pass


class TripDayRead(TripDayBase):
    id: uuid.UUID
    trip_id: uuid.UUID
    day_index: int
    items: list[TripItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class TripBase(BaseModel):
    title: str = Field(..., max_length=100)
    start_date: date
    end_date: date
    traveler_count: int = Field(1, gt=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    budget: Decimal | None = None
    status: TripStatus = TripStatus.DRAFT
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "TripBase":
        if self.start_date and self.end_date:
            assert self.start_date <= self.end_date, (
                "start_date cannot be after end_date"
            )
        return self


class TripCreate(TripBase):
    destination_ids: list[uuid.UUID] = Field(default_factory=list)


class TripUpdate(BaseModel):
    title: str | None = Field(None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    traveler_count: int | None = Field(None, gt=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    budget: Decimal | None = None
    status: TripStatus | None = None
    notes: str | None = None
    destination_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "TripUpdate":
        if self.start_date and self.end_date:
            assert self.start_date <= self.end_date, (
                "start_date cannot be after end_date"
            )
        return self


class TripRead(TripBase):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    guest_token: str | None = None
    days: list[TripDayRead] = []
    items: list[TripItemRead] = []  # items not attached to a day

    model_config = ConfigDict(from_attributes=True)
