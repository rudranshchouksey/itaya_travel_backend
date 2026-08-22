import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.experiences.schemas import ExperienceRead
from app.modules.listings.schemas import ListingRead


class SearchParams(BaseModel):
    query: str | None = None
    destination_id: uuid.UUID | None = None
    type: Literal["listing", "experience", "all"] = "all"
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)
    sort_by: Literal["price_asc", "price_desc", "newest", "relevance"] = "relevance"
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class SearchResultItem(BaseModel):
    item_type: Literal["listing", "experience"]
    item_id: uuid.UUID
    relevance_score: float = 1.0
    data: ListingRead | ExperienceRead | dict


class SearchResponse(BaseModel):
    total_count: int
    results: list[SearchResultItem]
