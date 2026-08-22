from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.experiences.models import Experience, ExperienceStatus
from app.modules.listings.models import Listing, ListingStatus
from app.modules.recommendations.schemas import (
    RecommendationPreferences,
    RecommendationResponse,
    RecommendationResultItem,
)


class RecommendationServiceInterface(ABC):
    @abstractmethod
    async def get_recommendations(
        self, session: AsyncSession, preferences: RecommendationPreferences
    ) -> RecommendationResponse:
        pass


class DeterministicRecommendationService(RecommendationServiceInterface):
    async def get_recommendations(
        self, session: AsyncSession, preferences: RecommendationPreferences
    ) -> RecommendationResponse:
        results = []

        # 1. Fetch Listings
        stmt = (
            select(Listing)
            .options(selectinload(Listing.images))
            .where(Listing.status == ListingStatus.PUBLISHED)
        )

        if preferences.destination_id:
            stmt = stmt.where(Listing.destination_id == preferences.destination_id)

        if preferences.preferred_types:
            stmt = stmt.where(Listing.property_type.in_(preferences.preferred_types))

        # We'll just fetch a limit to mock recommendations and score them.
        stmt = stmt.limit(preferences.limit)

        listings = (await session.execute(stmt)).scalars().all()

        for listing in listings:
            # Deterministic scoring logic:
            # Base score = 1.0
            # If destination matches perfectly = + 2.0
            # (If budget logic applied, we'd adjust score based on proximity to budget)
            score = 1.0
            if (
                preferences.destination_id
                and listing.destination_id == preferences.destination_id
            ):
                score += 2.0

            results.append(
                RecommendationResultItem(
                    item_type="listing",
                    item_id=listing.id,
                    score=score,
                    data={
                        "title": listing.title,
                        "property_type": listing.property_type,
                        "destination_id": listing.destination_id,
                    },
                )
            )

        # 2. Fetch Experiences
        exp_stmt = (
            select(Experience)
            .options(selectinload(Experience.images))
            .where(Experience.status == ExperienceStatus.PUBLISHED)
        )
        if preferences.destination_id:
            exp_stmt = exp_stmt.where(
                Experience.destination_id == preferences.destination_id
            )

        exp_stmt = exp_stmt.limit(preferences.limit)
        experiences = (await session.execute(exp_stmt)).scalars().all()

        for exp in experiences:
            score = 1.0
            if (
                preferences.destination_id
                and exp.destination_id == preferences.destination_id
            ):
                score += 2.0

            results.append(
                RecommendationResultItem(
                    item_type="experience",
                    item_id=exp.id,
                    score=score,
                    data={
                        "title": exp.title,
                        "base_price": float(exp.base_price),
                        "destination_id": exp.destination_id,
                    },
                )
            )

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        return RecommendationResponse(results=results[: preferences.limit])


recommendation_service = DeterministicRecommendationService()
