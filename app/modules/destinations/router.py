from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.modules.destinations.schemas import DestinationRead, DestinationSummary
from app.modules.destinations.service import DestinationService

router = APIRouter()


@router.get("", response_model=list[DestinationSummary])
async def get_destinations(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, min_length=2, max_length=100),
    country: str | None = None,
) -> Sequence[DestinationSummary]:
    destinations = await DestinationService.get_destinations(
        session=session, skip=skip, limit=limit, search=search, country=country
    )
    return destinations


@router.get("/{slug}", response_model=DestinationRead)
async def get_destination_by_slug(slug: str, session: SessionDep) -> DestinationRead:
    destination = await DestinationService.get_by_slug(session, slug=slug)
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )
    return destination


@router.get("/{slug}/summary", response_model=DestinationSummary)
async def get_destination_summary_by_slug(
    slug: str, session: SessionDep
) -> DestinationSummary:
    destination = await DestinationService.get_by_slug(session, slug=slug)
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found",
        )
    return destination
