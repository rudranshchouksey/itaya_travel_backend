import uuid
from collections.abc import Sequence
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep
from app.modules.listings.models import PropertyType
from app.modules.listings.schemas import (
    AvailabilityQueryParams,
    ListingAvailabilityRead,
    ListingRead,
    ListingSummary,
)
from app.modules.listings.service import ListingService

router = APIRouter()


@router.get("", response_model=list[ListingSummary])
async def get_listings(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    destination_id: uuid.UUID | None = None,
    property_type: PropertyType | None = None,
    guest_capacity: int | None = Query(None, ge=1),
) -> Sequence[ListingSummary]:
    listings = await ListingService.get_listings(
        session=session,
        skip=skip,
        limit=limit,
        destination_id=destination_id,
        property_type=property_type,
        guest_capacity=guest_capacity,
        public_only=True,
    )
    return listings


@router.get("/{slug}", response_model=ListingRead)
async def get_listing_by_slug(slug: str, session: SessionDep) -> ListingRead:
    listing = await ListingService.get_by_slug(session, slug=slug, public_only=True)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    return listing


@router.get("/{id}/availability", response_model=list[ListingAvailabilityRead])
async def get_listing_availability(
    id: uuid.UUID,
    session: SessionDep,
    params: AvailabilityQueryParams = Depends(),  # noqa: B008
) -> Sequence[ListingAvailabilityRead]:
    if params.end_date < params.start_date:
        raise HTTPException(
            status_code=400, detail="end_date cannot be before start_date"
        )
    if params.start_date < date.today():  # noqa: DTZ011
        raise HTTPException(status_code=400, detail="start_date cannot be in the past")

    availabilities = await ListingService.get_availability(
        session=session,
        listing_id=id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    return availabilities
