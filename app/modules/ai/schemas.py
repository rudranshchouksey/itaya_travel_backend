import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class AITripPlanRequest(BaseModel):
    destination_id: uuid.UUID
    start_date: date
    end_date: date
    budget: float | None = Field(None, ge=0)
    traveler_count: int = Field(1, ge=1)
    travel_style: Literal["relaxed", "balanced", "packed"] = "balanced"
    interests: list[str] = Field(default_factory=list)
    preferred_accommodation: Literal["hotel", "hostel", "apartment", "villa", "any"] = "any"
    free_form_request: str | None = None

class AITripOptimizationRequest(BaseModel):
    trip_id: uuid.UUID
    instruction: str
    target_budget: float | None = None

class AIProposedTripItem(BaseModel):
    item_type: Literal["stay", "experience", "transport", "activity", "custom"]
    title: str
    notes: str | None = None
    estimated_cost: float | None = None
    listing_id: uuid.UUID | None = None
    experience_id: uuid.UUID | None = None

class AIProposedTripDay(BaseModel):
    date: date
    title: str
    items: list[AIProposedTripItem]

class AITripPlanResponse(BaseModel):
    title: str
    destination_id: uuid.UUID
    start_date: date
    end_date: date
    total_estimated_budget: float
    explanation: str
    days: list[AIProposedTripDay]
