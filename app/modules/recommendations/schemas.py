import uuid
from typing import Literal

from pydantic import BaseModel, Field
from fastapi import Query

class RecommendationPreferences(BaseModel):
    destination_id: uuid.UUID | None = None
    preferred_budget: float | None = Field(None, ge=0)
    preferred_types: list[Literal["hotel", "hostel", "apartment", "villa"]] | None = Query(None)
    limit: int = Field(10, ge=1, le=50)


class RecommendationResultItem(BaseModel):
    item_type: Literal["listing", "experience", "destination"]
    item_id: uuid.UUID
    score: float
    data: dict


class RecommendationResponse(BaseModel):
    results: list[RecommendationResultItem]
