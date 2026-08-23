import logging
import random
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reviews.models import Review
from app.modules.bookings.models import Booking, BookingStatus, BookingItem
from app.modules.trips.models import TripItemType
from .utils import generate_deterministic_uuid

logger = logging.getLogger(__name__)

REVIEW_BODIES = [
    "Amazing experience, highly recommended!",
    "Great place, very clean and comfortable.",
    "The host was very accommodating and the location was perfect.",
    "Good value for money, but could use some updates.",
    "Absolutely breathtaking views. Will come back again.",
    "A bit noisy at night, but otherwise a pleasant stay.",
    "One of the best experiences of my life!",
    "Decent stay, matched the description.",
]

async def seed_reviews(session: AsyncSession, bookings: list[Booking]) -> int:
    """Seed demo reviews idempotently."""
    
    count = 0
    
    for i, b in enumerate(bookings):
        # Only seed reviews for completed bookings
        if b.booking_status != BookingStatus.COMPLETED:
            continue
            
        # Fetch items explicitly to avoid async lazy loading MissingGreenlet
        result = await session.execute(
            select(BookingItem).where(BookingItem.booking_id == b.id)
        )
        items = result.scalars().all()
            
        for item in items:
            # Check if review exists for this user and item
            result = await session.execute(
                select(Review).where(Review.user_id == b.user_id, Review.booking_item_id == item.id)
            )
            existing = result.scalars().first()
            
            if not existing:
                review_id = generate_deterministic_uuid("review", str(item.id))
                
                # Deterministic rating and body
                rating = (i % 3) + 3  # Ratings between 3 and 5
                body = REVIEW_BODIES[i % len(REVIEW_BODIES)]
                title = f"{rating} Star Review"
                
                existing = Review(
                    id=review_id,
                    user_id=b.user_id,
                    booking_item_id=item.id,
                    listing_id=item.listing_id if item.item_type == TripItemType.STAY else None,
                    experience_id=item.experience_id if item.item_type == TripItemType.EXPERIENCE else None,
                    rating=rating,
                    title=title,
                    body=body,
                    images=[]
                )
                session.add(existing)
                count += 1
                
    await session.commit()
    logger.info(f"Seeded {count} reviews.")
    return count

async def clean_demo_reviews(session: AsyncSession) -> int:
    """Reviews are cleaned automatically via CASCADE when users/bookings are deleted. This is a no-op fallback."""
    return 0
