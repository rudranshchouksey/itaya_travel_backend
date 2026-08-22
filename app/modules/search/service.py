from abc import ABC, abstractmethod
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.experiences.models import Experience, ExperienceStatus
from app.modules.listings.models import Listing, ListingStatus
from app.modules.search.schemas import SearchParams, SearchResponse, SearchResultItem


class SearchServiceInterface(ABC):
    @abstractmethod
    async def search(
        self, session: AsyncSession, params: SearchParams
    ) -> SearchResponse:
        pass


class PostgresSearchService(SearchServiceInterface):
    async def search(
        self, session: AsyncSession, params: SearchParams
    ) -> SearchResponse:
        results: list[SearchResultItem] = []

        limit_per_type = (
            params.limit if params.type != "all" else max(1, params.limit // 2)
        )

        # 1. Search Listings
        if params.type in ["listing", "all"]:
            stmt = (
                select(Listing)
                .options(selectinload(Listing.images), selectinload(Listing.amenities))
                .where(Listing.status == ListingStatus.PUBLISHED)
            )

            if params.query:
                q = f"%{params.query}%"
                stmt = stmt.where(
                    or_(Listing.title.ilike(q), Listing.description.ilike(q))
                )

            if params.destination_id:
                stmt = stmt.where(Listing.destination_id == params.destination_id)

            if params.sort_by == "newest":
                stmt = stmt.order_by(Listing.created_at.desc())

            # Basic subquery to find listings with matching availability/prices
            # For simplicity, we just filter by the availability price limits and join
            # but right now we don't strictly require availability checks for a "basic" search
            # We'll just enforce it if min_price or max_price is provided

            # For budget filter, we would join Availability. Since it's a basic search,
            # we can just fetch and filter in python if needed, or join properly.
            # We'll skip complex price sorting in DB for this Phase 9 "foundation".

            stmt = stmt.offset(params.skip).limit(limit_per_type)
            listings = (await session.execute(stmt)).scalars().all()

            for listing in listings:
                # We mock relevance or price checks
                results.append(
                    SearchResultItem(
                        item_type="listing",
                        item_id=listing.id,
                        relevance_score=1.0,
                        data={
                            "id": listing.id,
                            "title": listing.title,
                            "slug": listing.slug,
                            "description": listing.description,
                            "property_type": listing.property_type,
                            "guest_capacity": listing.guest_capacity,
                            "bedrooms": listing.bedrooms,
                            "beds": listing.beds,
                            "bathrooms": listing.bathrooms,
                            "latitude": listing.latitude,
                            "longitude": listing.longitude,
                            "status": listing.status,
                            "verification_status": listing.verification_status,
                            "created_at": listing.created_at,
                            "updated_at": listing.updated_at,
                            "host_id": listing.host_id,
                            "destination_id": listing.destination_id,
                            "images": [],
                            "amenities": [],
                        },
                    )
                )

        # 2. Search Experiences
        if params.type in ["experience", "all"]:
            stmt = (
                select(Experience)
                .options(
                    selectinload(Experience.images), selectinload(Experience.categories)
                )
                .where(Experience.status == ExperienceStatus.PUBLISHED)
            )

            if params.query:
                q = f"%{params.query}%"
                stmt = stmt.where(
                    or_(Experience.title.ilike(q), Experience.description.ilike(q))
                )

            if params.destination_id:
                stmt = stmt.where(Experience.destination_id == params.destination_id)

            if params.min_price is not None:
                stmt = stmt.where(
                    Experience.base_price >= Decimal(str(params.min_price))
                )

            if params.max_price is not None:
                stmt = stmt.where(
                    Experience.base_price <= Decimal(str(params.max_price))
                )

            if params.sort_by == "newest":
                stmt = stmt.order_by(Experience.created_at.desc())
            elif params.sort_by == "price_asc":
                stmt = stmt.order_by(Experience.base_price.asc())
            elif params.sort_by == "price_desc":
                stmt = stmt.order_by(Experience.base_price.desc())

            stmt = stmt.offset(params.skip).limit(limit_per_type)
            experiences = (await session.execute(stmt)).scalars().all()

            for exp in experiences:
                results.append(
                    SearchResultItem(
                        item_type="experience",
                        item_id=exp.id,
                        relevance_score=1.0,
                        data={
                            "id": exp.id,
                            "title": exp.title,
                            "slug": exp.slug,
                            "description": exp.description,
                            "duration_minutes": exp.duration_minutes,
                            "guest_capacity": exp.guest_capacity,
                            "base_price": exp.base_price,
                            "currency": exp.currency,
                            "meeting_point": exp.meeting_point,
                            "status": exp.status,
                            "verification_status": exp.verification_status,
                            "created_at": exp.created_at,
                            "updated_at": exp.updated_at,
                            "provider_id": exp.provider_id,
                            "destination_id": exp.destination_id,
                            "images": [],
                            "categories": [],
                        },
                    )
                )

        # Combine and mock sort by relevance if needed
        # In a real app, this would be heavily relying on Postgres ts_rank or OpenSearch scores
        if params.sort_by == "relevance":
            pass  # keep as is for now

        return SearchResponse(total_count=len(results), results=results)


search_service = PostgresSearchService()
