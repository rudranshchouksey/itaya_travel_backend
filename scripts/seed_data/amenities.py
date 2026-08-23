import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.listings.models import Amenity
from .utils import generate_deterministic_uuid

logger = logging.getLogger(__name__)

AMENITIES = [
    "WiFi",
    "Pool",
    "Parking",
    "Air conditioning",
    "Breakfast",
    "Kitchen",
    "Workspace",
    "Gym",
    "Spa",
    "Pet friendly",
    "Mountain view",
    "Beach access",
    "Room service",
    "Bar",
    "Restaurant",
]

async def seed_amenities(session: AsyncSession) -> int:
    """Seed base amenities idempotently."""
    count = 0
    for name in AMENITIES:
        # Check if exists
        result = await session.execute(select(Amenity).where(Amenity.name == name))
        existing = result.scalars().first()
        if not existing:
            amenity_id = generate_deterministic_uuid("amenity", name)
            new_amenity = Amenity(id=amenity_id, name=name)
            session.add(new_amenity)
            count += 1
    
    await session.commit()
    logger.info(f"Seeded {count} amenities.")
    return count

async def clean_demo_amenities(session: AsyncSession) -> int:
    # Amenities are reference data, no "demo" cleanup required unless we explicitly created demo-specific ones.
    return 0
