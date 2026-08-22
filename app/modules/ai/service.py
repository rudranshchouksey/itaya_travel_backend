import uuid
from datetime import timedelta
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.recommendations.schemas import RecommendationPreferences
from app.modules.recommendations.service import recommendation_service

from .schemas import (
    AIProposedTripDay,
    AIProposedTripItem,
    AITripOptimizationRequest,
    AITripPlanRequest,
    AITripPlanResponse,
)


class AIServiceInterface(Protocol):
    async def plan_trip(
        self, session: AsyncSession, request: AITripPlanRequest
    ) -> AITripPlanResponse: ...

    async def optimize_trip(
        self, session: AsyncSession, request: AITripOptimizationRequest
    ) -> AITripPlanResponse: ...


class MockAIService:
    async def plan_trip(
        self, session: AsyncSession, request: AITripPlanRequest
    ) -> AITripPlanResponse:
        # Simulate LLM intent extraction by querying recommendations for this destination
        prefs = RecommendationPreferences(
            destination_id=request.destination_id,
            preferred_budget=request.budget,
            limit=20,
        )
        if request.preferred_accommodation != "any":
            prefs.preferred_types = [request.preferred_accommodation]  # type: ignore

        recs = await recommendation_service.get_recommendations(session, prefs)

        # Build deterministic mock itinerary
        days = []
        current_date = request.start_date
        total_budget = 0.0

        # Pull out stays and experiences
        stays = [r for r in recs.results if r.item_type == "listing"]
        experiences = [r for r in recs.results if r.item_type == "experience"]

        # Assign a stay if available
        primary_stay = stays[0] if stays else None

        day_index = 1
        while current_date <= request.end_date:
            items = []
            if primary_stay and current_date == request.start_date:
                items.append(
                    AIProposedTripItem(
                        item_type="stay",
                        title=f"Check-in at {primary_stay.title}",
                        notes="Recommended based on your accommodation preferences.",
                        estimated_cost=primary_stay.data.get("price_per_night"),
                        listing_id=primary_stay.id,
                    )
                )
                if primary_stay.data.get("price_per_night"):
                    total_budget += float(primary_stay.data.get("price_per_night"))

            # Add an experience each day if we have enough
            if experiences:
                exp = experiences.pop(0) if experiences else None
                if exp:
                    items.append(
                        AIProposedTripItem(
                            item_type="experience",
                            title=exp.title,
                            notes=f"A great activity matching your {request.travel_style} style.",
                            estimated_cost=exp.data.get("price"),
                            experience_id=exp.id,
                        )
                    )
                    if exp.data.get("price"):
                        total_budget += float(exp.data.get("price"))

            days.append(
                AIProposedTripDay(
                    date=current_date,
                    title=f"Day {day_index}: Exploration",
                    items=items,
                )
            )
            current_date += timedelta(days=1)
            day_index += 1

        return AITripPlanResponse(
            title=f"Your {request.travel_style.capitalize()} Trip",
            destination_id=request.destination_id,
            start_date=request.start_date,
            end_date=request.end_date,
            total_estimated_budget=total_budget,
            explanation="I have analyzed your intent and curated this itinerary using real Itvaya listings and experiences.",
            days=days,
        )

    async def optimize_trip(
        self, session: AsyncSession, request: AITripOptimizationRequest
    ) -> AITripPlanResponse:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.modules.trips.models import Trip

        # The AI must operate against the existing Trip model
        result = await session.execute(
            select(Trip)
            .options(selectinload(Trip.destinations))
            .where(Trip.id == request.trip_id)
        )
        trip = result.scalars().first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")

        return AITripPlanResponse(
            title=f"{trip.title} (Optimized)",
            destination_id=trip.destinations[0].id
            if trip.destinations
            else uuid.uuid4(),
            start_date=trip.start_date,
            end_date=trip.end_date,
            total_estimated_budget=request.target_budget or float(trip.budget or 0.0),
            explanation=f"Optimized trip based on instructions: {request.instruction}",
            days=[],
        )


ai_service = MockAIService()
