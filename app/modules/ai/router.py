from fastapi import APIRouter

from app.api.deps import SessionDep
from app.modules.ai.schemas import (
    AITripOptimizationRequest,
    AITripPlanRequest,
    AITripPlanResponse,
)
from app.modules.ai.service import ai_service

router = APIRouter(tags=["AI Planner"])

@router.post(
    "/ai/trips/plan",
    response_model=AITripPlanResponse,
    summary="Plan a trip using AI",
)
async def plan_trip(
    session: SessionDep,
    request: AITripPlanRequest,
):
    """
    Analyzes intent and proposes a structured trip itinerary based on real Itvaya inventory.
    """
    return await ai_service.plan_trip(session, request)

@router.post(
    "/ai/trips/optimize",
    response_model=AITripPlanResponse,
    summary="Optimize a trip using AI",
)
async def optimize_trip(
    session: SessionDep,
    request: AITripOptimizationRequest,
):
    """
    Optimizes an existing trip using natural language instructions.
    """
    return await ai_service.optimize_trip(session, request)
