import logging
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trips.models import (
    Trip, TripDay, TripItem, TripItemType, TripStatus, TripParticipant, TripParticipantRole, TripDestination
)
from app.modules.users.models import User
from app.modules.destinations.models import Destination
from app.modules.listings.models import Listing
from app.modules.experiences.models import Experience
from .utils import generate_deterministic_uuid

logger = logging.getLogger(__name__)

TRIP_TEMPLATES = [
    ("Goa Weekend", 3, "INR", 30000, "Relaxing weekend at the beach"),
    ("Himachal Adventure", 7, "INR", 50000, "Trekking and exploring mountains"),
    ("Rajasthan Heritage", 5, "INR", 40000, "Palaces and forts"),
    ("Bali Escape", 6, "USD", 1500, "Tropical vacation"),
    ("Japan Discovery", 10, "USD", 3500, "Culture and food"),
    ("Dubai Luxury Trip", 4, "AED", 10000, "Shopping and luxury"),
    ("Kerala Slow Travel", 8, "INR", 45000, "Backwaters and tea gardens"),
    ("European Summer", 14, "EUR", 4000, "Exploring multiple cities"),
]

async def seed_trips(
    session: AsyncSession, 
    travelers: list[User], 
    destinations: dict[str, Destination],
    listings: list[Listing],
    experiences: list[Experience]
) -> list[Trip]:
    """Seed demo trips idempotently."""
    
    seeded_trips = []
    dest_list = list(destinations.values())
    count = 0
    
    today = date.today()
    
    for i in range(25):
        traveler = travelers[i % len(travelers)]
        title, duration_days, currency, budget, notes = TRIP_TEMPLATES[i % len(TRIP_TEMPLATES)]
        
        # Unique title per traveler to act as idempotency key
        trip_title = f"[DEMO] {title} {i+1}"
        
        result = await session.execute(
            select(Trip).where(Trip.owner_id == traveler.id, Trip.title == trip_title)
        )
        existing = result.scalars().first()
        
        if not existing:
            trip_id = generate_deterministic_uuid("trip", f"{traveler.id}-{trip_title}")
            start_date = today + timedelta(days=(i * 10))
            end_date = start_date + timedelta(days=duration_days)
            
            existing = Trip(
                id=trip_id,
                owner_id=traveler.id,
                title=trip_title,
                start_date=start_date,
                end_date=end_date,
                traveler_count=2,
                currency=currency,
                budget=Decimal(str(budget)),
                status=TripStatus.PLANNED,
                notes=notes
            )
            session.add(existing)
            
            # Destination Link
            dest = dest_list[i % len(dest_list)]
            td = TripDestination(trip_id=trip_id, destination_id=dest.id)
            session.add(td)
            
            # Participant (Owner)
            part_id = generate_deterministic_uuid("trip_participant", f"{trip_id}-{traveler.id}")
            part = TripParticipant(
                id=part_id, trip_id=trip_id, user_id=traveler.id, 
                name=traveler.first_name, email=traveler.email, role=TripParticipantRole.OWNER
            )
            session.add(part)
            
            # Find relevant listing and experience
            valid_listings = [l for l in listings if l.destination_id == dest.id]
            valid_experiences = [e for e in experiences if e.destination_id == dest.id]
            
            # Days and Items
            for day_idx in range(duration_days):
                day_date = start_date + timedelta(days=day_idx)
                day_id = generate_deterministic_uuid("trip_day", f"{trip_id}-{day_idx}")
                
                day = TripDay(
                    id=day_id,
                    trip_id=trip_id,
                    date=day_date,
                    day_index=day_idx,
                    title=f"Day {day_idx + 1}"
                )
                session.add(day)
                
                # Add a Stay item if listing available
                if valid_listings and day_idx == 0:
                    l = valid_listings[0]
                    item_id = generate_deterministic_uuid("trip_item", f"{day_id}-stay")
                    item = TripItem(
                        id=item_id, trip_id=trip_id, trip_day_id=day_id,
                        item_type=TripItemType.STAY, title=f"Stay at {l.title}",
                        listing_id=l.id, order_index=0
                    )
                    session.add(item)
                    
                # Add an Experience item
                if valid_experiences and day_idx % 2 == 0:
                    e = valid_experiences[day_idx % len(valid_experiences)]
                    item_id = generate_deterministic_uuid("trip_item", f"{day_id}-exp")
                    item = TripItem(
                        id=item_id, trip_id=trip_id, trip_day_id=day_id,
                        item_type=TripItemType.EXPERIENCE, title=f"Activity: {e.title}",
                        experience_id=e.id, order_index=1
                    )
                    session.add(item)
                    
            count += 1
            
        seeded_trips.append(existing)
        
    await session.commit()
    logger.info(f"Seeded {count} trips with days and itinerary items.")
    return seeded_trips


async def clean_demo_trips(session: AsyncSession) -> int:
    """Delete all demo trips."""
    stmt = delete(Trip).where(Trip.title.like("[DEMO]%"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo trips.")
    return deleted_count
