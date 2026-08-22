import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.listings.models import ListingStatus, PropertyType, VerificationStatus


class AmenityRead(BaseModel):
    id: uuid.UUID
    name: str
    icon_url: str | None

    model_config = ConfigDict(from_attributes=True)


class ListingImageRead(BaseModel):
    id: uuid.UUID
    url: str
    is_primary: bool
    display_order: int

    model_config = ConfigDict(from_attributes=True)


class ListingAvailabilityRead(BaseModel):
    date: date
    price: Decimal
    is_available: bool

    model_config = ConfigDict(from_attributes=True)


class ListingSummary(BaseModel):
    id: uuid.UUID
    destination_id: uuid.UUID
    title: str
    slug: str
    property_type: PropertyType
    guest_capacity: int
    bedrooms: int
    beds: int
    bathrooms: float
    status: ListingStatus
    verification_status: VerificationStatus
    images: list[ListingImageRead] = []

    model_config = ConfigDict(from_attributes=True)


class ListingRead(ListingSummary):
    host_id: uuid.UUID
    description: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    amenities: list[AmenityRead] = []
    created_at: datetime
    updated_at: datetime


class ListingCreate(BaseModel):
    host_id: uuid.UUID
    destination_id: uuid.UUID
    title: str = Field(min_length=2, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)
    description: str | None = None
    property_type: PropertyType
    guest_capacity: int = Field(default=1, ge=1)
    bedrooms: int = Field(default=1, ge=0)
    beds: int = Field(default=1, ge=0)
    bathrooms: float = Field(default=1.0, ge=0.0)
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    status: ListingStatus = ListingStatus.DRAFT
    verification_status: VerificationStatus = VerificationStatus.PENDING


class AvailabilityQueryParams(BaseModel):
    start_date: date
    end_date: date
