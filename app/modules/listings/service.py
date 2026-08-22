import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.listings.models import (
    Listing,
    ListingAvailability,
    ListingStatus,
    PropertyType,
    VerificationStatus,
)
from app.modules.listings.schemas import ListingCreate


class ListingService:
    @staticmethod
    async def create_listing(
        session: AsyncSession, listing_in: ListingCreate
    ) -> Listing:
        listing = Listing(**listing_in.model_dump())
        session.add(listing)
        await session.commit()
        await session.refresh(listing)
        return listing

    @staticmethod
    async def get_by_slug(
        session: AsyncSession, slug: str, public_only: bool = True
    ) -> Listing | None:
        stmt = (
            select(Listing)
            .options(selectinload(Listing.images), selectinload(Listing.amenities))
            .where(Listing.slug == slug)
        )

        if public_only:
            stmt = stmt.where(
                and_(
                    Listing.status == ListingStatus.PUBLISHED,
                    Listing.verification_status == VerificationStatus.VERIFIED,
                )
            )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_listings(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        destination_id: uuid.UUID | None = None,
        property_type: PropertyType | None = None,
        guest_capacity: int | None = None,
        public_only: bool = True,
    ) -> Sequence[Listing]:
        stmt = (
            select(Listing)
            .options(selectinload(Listing.images))
            .offset(skip)
            .limit(limit)
        )

        if public_only:
            stmt = stmt.where(
                and_(
                    Listing.status == ListingStatus.PUBLISHED,
                    Listing.verification_status == VerificationStatus.VERIFIED,
                )
            )

        if destination_id:
            stmt = stmt.where(Listing.destination_id == destination_id)

        if property_type:
            stmt = stmt.where(Listing.property_type == property_type)

        if guest_capacity is not None:
            stmt = stmt.where(Listing.guest_capacity >= guest_capacity)

        # Order by created_at desc as default
        stmt = stmt.order_by(Listing.created_at.desc())

        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_availability(
        session: AsyncSession,
        listing_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Sequence[ListingAvailability]:
        # Filter for availability matrix between dates and only return true availabilities
        stmt = (
            select(ListingAvailability)
            .where(
                and_(
                    ListingAvailability.listing_id == listing_id,
                    ListingAvailability.date >= start_date,
                    ListingAvailability.date <= end_date,
                    ListingAvailability.is_available == True,
                )
            )
            .order_by(ListingAvailability.date)
        )

        result = await session.execute(stmt)
        return result.scalars().all()
