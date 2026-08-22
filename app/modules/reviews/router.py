import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, get_current_active_user
from app.modules.reviews.schemas import ReviewCreate, ReviewRead
from app.modules.reviews.service import ReviewService
from app.modules.users.models import User

router = APIRouter(tags=["Reviews"])


@router.post(
    "/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new review",
)
async def create_review(
    review_in: ReviewCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Submit a review for a completed booking item.
    """
    return await ReviewService.create_review(
        session=session,
        user_id=current_user.id,
        review_in=review_in,
    )


@router.get(
    "/listings/{listing_id}/reviews",
    response_model=list[ReviewRead],
    summary="Get listing reviews",
)
async def get_listing_reviews(
    listing_id: uuid.UUID,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Retrieve reviews for a listing.
    """
    return await ReviewService.get_listing_reviews(session, listing_id, skip, limit)


@router.get(
    "/experiences/{experience_id}/reviews",
    response_model=list[ReviewRead],
    summary="Get experience reviews",
)
async def get_experience_reviews(
    experience_id: uuid.UUID,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Retrieve reviews for an experience.
    """
    return await ReviewService.get_experience_reviews(session, experience_id, skip, limit)
