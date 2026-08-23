import logging
from datetime import date, timedelta, time
from decimal import Decimal
import random
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import (
    Booking, BookingItem, BookingGuest, BookingStatus
)
from app.modules.trips.models import TripItemType
from app.modules.users.models import User
from app.modules.listings.models import Listing
from app.modules.experiences.models import Experience
from .utils import generate_deterministic_uuid

logger = logging.getLogger(__name__)

async def seed_bookings(
    session: AsyncSession, 
    travelers: list[User], 
    listings: list[Listing],
    experiences: list[Experience]
) -> list[Booking]:
    """Seed demo bookings idempotently."""
    
    seeded_bookings = []
    count = 0
    today = date.today()
    
    # Generate 30 bookings
    for i in range(30):
        traveler = travelers[i % len(travelers)]
        ref = f"DEMO-BKG-{i+1:04d}"
        
        result = await session.execute(select(Booking).where(Booking.reference == ref))
        existing = result.scalars().first()
        
        if not existing:
            book_id = generate_deterministic_uuid("booking", ref)
            
            # Determine status deterministically
            status_map = [
                BookingStatus.COMPLETED, BookingStatus.CONFIRMED, BookingStatus.PENDING,
                BookingStatus.CANCELLED, BookingStatus.COMPLETED, BookingStatus.FAILED
            ]
            status = status_map[i % len(status_map)]
            
            # Is it a stay or experience?
            is_stay = (i % 2 == 0)
            
            subtotal = Decimal('0.00')
            
            if is_stay and listings:
                listing = listings[i % len(listings)]
                start_d = today + timedelta(days=(i * 2))
                if status == BookingStatus.COMPLETED:
                    start_d = today - timedelta(days=30 + i)
                    
                end_d = start_d + timedelta(days=3)
                price = listing.guest_capacity * 1000
                subtotal = Decimal(str(price * 3))
                
                item_id = generate_deterministic_uuid("booking_item", f"{ref}-stay")
                item = BookingItem(
                    id=item_id, booking_id=book_id, item_type=TripItemType.STAY,
                    listing_id=listing.id, provider_id=listing.host_id,
                    start_date=start_d, end_date=end_d,
                    quantity=1, guest_count=2,
                    price_snapshot=Decimal(str(price)), subtotal=subtotal,
                    taxes=Decimal('0.00'), fees=Decimal('0.00'), total=subtotal
                )
            elif experiences:
                exp = experiences[i % len(experiences)]
                start_d = today + timedelta(days=(i * 2))
                if status == BookingStatus.COMPLETED:
                    start_d = today - timedelta(days=30 + i)
                    
                price = exp.base_price
                subtotal = price * 2
                
                item_id = generate_deterministic_uuid("booking_item", f"{ref}-exp")
                item = BookingItem(
                    id=item_id, booking_id=book_id, item_type=TripItemType.EXPERIENCE,
                    experience_id=exp.id, provider_id=exp.provider_id,
                    start_date=start_d, start_time=time(9,0),
                    quantity=1, guest_count=2,
                    price_snapshot=price, subtotal=subtotal,
                    taxes=Decimal('0.00'), fees=Decimal('0.00'), total=subtotal
                )
            else:
                continue
                
            platform_fee = subtotal * Decimal('0.10')
            taxes = subtotal * Decimal('0.05')
            total = subtotal + taxes
            provider_amt = subtotal - platform_fee
            
            existing = Booking(
                id=book_id,
                user_id=traveler.id,
                reference=ref,
                currency="INR",
                subtotal=subtotal,
                fees=Decimal('0.00'),
                platform_fee=platform_fee,
                provider_amount=provider_amt,
                taxes=taxes,
                discounts=Decimal('0.00'),
                total=total,
                booking_status=status
            )
            session.add(existing)
            session.add(item)
            
            # Guest
            guest_id = generate_deterministic_uuid("booking_guest", ref)
            guest = BookingGuest(
                id=guest_id, booking_id=book_id,
                first_name=traveler.first_name, last_name=traveler.last_name,
                email=traveler.email, is_primary=True
            )
            session.add(guest)
            
            count += 1
            
        seeded_bookings.append(existing)
        
    await session.commit()
    logger.info(f"Seeded {count} bookings with items and guests.")
    return seeded_bookings

async def clean_demo_bookings(session: AsyncSession) -> int:
    """Delete all demo bookings."""
    stmt = delete(Booking).where(Booking.reference.like("DEMO-BKG-%"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo bookings.")
    return deleted_count
