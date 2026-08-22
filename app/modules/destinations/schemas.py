import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DestinationBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)
    country: str = Field(min_length=2, max_length=100)
    state_province_region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)

    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    timezone: str | None = Field(default=None, max_length=50)

    hero_image_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class DestinationSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    country: str
    state_province_region: str | None
    city: str | None
    short_description: str | None
    hero_image_url: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DestinationCreate(DestinationBase):
    description: str | None = None
    short_description: str | None = Field(default=None, max_length=500)


class DestinationRead(DestinationSummary):
    description: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    created_at: datetime
    updated_at: datetime
