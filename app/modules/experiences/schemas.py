import uuid
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.experiences.models import (
    ExperienceStatus,
    ExperienceVerificationStatus,
)


class ExperienceCategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    icon_url: str | None

    model_config = ConfigDict(from_attributes=True)


class ExperienceImageRead(BaseModel):
    id: uuid.UUID
    url: str
    is_primary: bool
    display_order: int

    model_config = ConfigDict(from_attributes=True)


class ExperienceAvailabilityRead(BaseModel):
    id: uuid.UUID
    date: date
    start_time: time
    end_time: time
    price_override: Decimal | None
    is_available: bool

    model_config = ConfigDict(from_attributes=True)


class ExperienceSummary(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    destination_id: uuid.UUID
    title: str
    slug: str
    duration_minutes: int
    guest_capacity: int
    base_price: Decimal
    currency: str
    status: ExperienceStatus
    verification_status: ExperienceVerificationStatus
    categories: list[ExperienceCategoryRead] = []
    images: list[ExperienceImageRead] = []

    model_config = ConfigDict(from_attributes=True)


class ExperienceRead(ExperienceSummary):
    description: str | None
    meeting_point: str | None


class ExperienceCreate(BaseModel):
    destination_id: uuid.UUID
    title: str = Field(min_length=2, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    guest_capacity: int = Field(gt=0)
    base_price: Decimal = Field(ge=0.0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    meeting_point: str | None = None
    status: ExperienceStatus = ExperienceStatus.DRAFT
    category_ids: list[uuid.UUID] = []


class ExperienceUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    duration_minutes: int | None = Field(None, gt=0)
    guest_capacity: int | None = Field(None, gt=0)
    base_price: Decimal | None = Field(None, ge=0.0)
    meeting_point: str | None = None
    category_ids: list[uuid.UUID] | None = None


class AvailabilityBlockCreate(BaseModel):
    date: date
    start_time: time
    end_time: time
    price_override: Decimal | None = Field(default=None, ge=0.0)
    is_available: bool = True
