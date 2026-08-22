from fastapi import APIRouter, Depends, Query
from typing import Literal
import uuid

from app.api.deps import SessionDep
from app.modules.recommendations.schemas import (
    RecommendationPreferences,
    RecommendationResponse,
)
from app.modules.recommendations.service import recommendation_service

router = APIRouter(tags=["Recommendations"])

@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Get recommendations",
)
async def get_recommendations(
    session: SessionDep,
    destination_id: uuid.UUID | None = None,
    preferred_budget: float | None = Query(None, ge=0),
    preferred_types: list[Literal["hotel", "hostel", "apartment", "villa"]] | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Get deterministic recommendations based on preferences.
    """
    prefs = RecommendationPreferences(
        destination_id=destination_id,
        preferred_budget=preferred_budget,
        preferred_types=preferred_types,
        limit=limit
    )
    return await recommendation_service.get_recommendations(session, prefs)
