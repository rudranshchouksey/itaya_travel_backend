import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.modules.bookings.models import BookingItem, BookingStatus
from app.modules.reviews.models import Review
from app.modules.reviews.schemas import ReviewCreate
from app.modules.trips.models import TripItemType


class ReviewService:
    @staticmethod
    async def create_review(
        session: AsyncSession,
        user_id: uuid.UUID,
        review_in: ReviewCreate,
    ) -> Review:
        # Check if booking item exists
        stmt = (
            select(BookingItem)
            .options(selectinload(BookingItem.booking))
            .where(BookingItem.id == review_in.booking_item_id)
        )
        booking_item = (await session.execute(stmt)).scalar_one_or_none()

        if not booking_item:
            raise NotFoundError("Booking item not found")

        # Check ownership
        if booking_item.booking.user_id != user_id:
            raise PermissionDeniedError("You do not own this booking")

        # Check if booking is completed
        if booking_item.booking.booking_status != BookingStatus.COMPLETED:
            raise ValidationError("You can only review completed bookings")

        # Check for duplicates
        existing_stmt = (
            select(Review)
            .where(Review.user_id == user_id)
            .where(Review.booking_item_id == review_in.booking_item_id)
        )
        existing_review = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing_review:
            raise ValidationError("You have already reviewed this booking item")

        # Determine target
        listing_id = None
        experience_id = None
        if booking_item.item_type == TripItemType.STAY:
            listing_id = booking_item.listing_id
        elif booking_item.item_type == TripItemType.EXPERIENCE:
            experience_id = booking_item.experience_id
        else:
            raise ValidationError("This item type cannot be reviewed")

        review_db = Review(
            user_id=user_id,
            booking_item_id=booking_item.id,
            listing_id=listing_id,
            experience_id=experience_id,
            rating=review_in.rating,
            title=review_in.title,
            body=review_in.body,
            images=review_in.images,
        )

        session.add(review_db)
        await session.commit()
        await session.refresh(review_db)
        return review_db

    @staticmethod
    async def get_listing_reviews(
        session: AsyncSession, listing_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[Review]:
        stmt = (
            select(Review)
            .where(Review.listing_id == listing_id)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_experience_reviews(
        session: AsyncSession, experience_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[Review]:
        stmt = (
            select(Review)
            .where(Review.experience_id == experience_id)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
