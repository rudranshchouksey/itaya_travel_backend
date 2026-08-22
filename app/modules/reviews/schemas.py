import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    booking_item_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(None, max_length=100)
    body: str | None = Field(None)
    images: list[dict[str, Any]] = Field(default_factory=list)


class ReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    booking_item_id: uuid.UUID
    listing_id: uuid.UUID | None
    experience_id: uuid.UUID | None
    rating: int
    title: str | None
    body: str | None
    images: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
