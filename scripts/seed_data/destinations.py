import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.destinations.models import Destination
from .utils import generate_deterministic_uuid, get_demo_image_url

logger = logging.getLogger(__name__)

DEMO_DESTINATIONS = [
    # India
    {"name": "Goa", "slug": "demo-goa", "country": "India", "state": "Goa", "city": "Panaji", "lat": 15.2993, "lon": 74.1240, "tz": "Asia/Kolkata"},
    {"name": "Manali", "slug": "demo-manali", "country": "India", "state": "Himachal Pradesh", "city": "Manali", "lat": 32.2396, "lon": 77.1887, "tz": "Asia/Kolkata"},
    {"name": "Leh", "slug": "demo-leh", "country": "India", "state": "Ladakh", "city": "Leh", "lat": 34.1526, "lon": 77.5771, "tz": "Asia/Kolkata"},
    {"name": "Jaipur", "slug": "demo-jaipur", "country": "India", "state": "Rajasthan", "city": "Jaipur", "lat": 26.9124, "lon": 75.7873, "tz": "Asia/Kolkata"},
    {"name": "Udaipur", "slug": "demo-udaipur", "country": "India", "state": "Rajasthan", "city": "Udaipur", "lat": 24.5854, "lon": 73.7125, "tz": "Asia/Kolkata"},
    {"name": "Rishikesh", "slug": "demo-rishikesh", "country": "India", "state": "Uttarakhand", "city": "Rishikesh", "lat": 30.0869, "lon": 78.2676, "tz": "Asia/Kolkata"},
    {"name": "Kerala", "slug": "demo-kerala", "country": "India", "state": "Kerala", "city": "Kochi", "lat": 9.9312, "lon": 76.2673, "tz": "Asia/Kolkata"},
    {"name": "Mumbai", "slug": "demo-mumbai", "country": "India", "state": "Maharashtra", "city": "Mumbai", "lat": 19.0760, "lon": 72.8777, "tz": "Asia/Kolkata"},
    {"name": "Delhi", "slug": "demo-delhi", "country": "India", "state": "Delhi", "city": "New Delhi", "lat": 28.6139, "lon": 77.2090, "tz": "Asia/Kolkata"},
    {"name": "Varanasi", "slug": "demo-varanasi", "country": "India", "state": "Uttar Pradesh", "city": "Varanasi", "lat": 25.3176, "lon": 82.9739, "tz": "Asia/Kolkata"},
    
    # International
    {"name": "Dubai", "slug": "demo-dubai", "country": "United Arab Emirates", "state": "Dubai", "city": "Dubai", "lat": 25.2048, "lon": 55.2708, "tz": "Asia/Dubai"},
    {"name": "Bali", "slug": "demo-bali", "country": "Indonesia", "state": "Bali", "city": "Denpasar", "lat": -8.4095, "lon": 115.1889, "tz": "Asia/Makassar"},
    {"name": "Bangkok", "slug": "demo-bangkok", "country": "Thailand", "state": "Bangkok", "city": "Bangkok", "lat": 13.7563, "lon": 100.5018, "tz": "Asia/Bangkok"},
    {"name": "Singapore", "slug": "demo-singapore", "country": "Singapore", "state": "Singapore", "city": "Singapore", "lat": 1.3521, "lon": 103.8198, "tz": "Asia/Singapore"},
    {"name": "Tokyo", "slug": "demo-tokyo", "country": "Japan", "state": "Tokyo", "city": "Tokyo", "lat": 35.6762, "lon": 139.6503, "tz": "Asia/Tokyo"},
    {"name": "Paris", "slug": "demo-paris", "country": "France", "state": "Île-de-France", "city": "Paris", "lat": 48.8566, "lon": 2.3522, "tz": "Europe/Paris"},
    {"name": "London", "slug": "demo-london", "country": "United Kingdom", "state": "England", "city": "London", "lat": 51.5072, "lon": -0.1276, "tz": "Europe/London"},
    {"name": "Istanbul", "slug": "demo-istanbul", "country": "Turkey", "state": "Istanbul", "city": "Istanbul", "lat": 41.0082, "lon": 28.9784, "tz": "Europe/Istanbul"},
    {"name": "Maldives", "slug": "demo-maldives", "country": "Maldives", "state": "Malé", "city": "Malé", "lat": 4.1755, "lon": 73.5093, "tz": "Indian/Maldives"},
    {"name": "Barcelona", "slug": "demo-barcelona", "country": "Spain", "state": "Catalonia", "city": "Barcelona", "lat": 41.3851, "lon": 2.1734, "tz": "Europe/Madrid"},
]

async def seed_destinations(session: AsyncSession) -> dict[str, Destination]:
    """Seed demo destinations idempotently."""
    
    seeded = {}
    
    for d in DEMO_DESTINATIONS:
        result = await session.execute(select(Destination).where(Destination.slug == d["slug"]))
        existing = result.scalars().first()
        
        if not existing:
            dest_id = generate_deterministic_uuid("destination", d["slug"])
            existing = Destination(
                id=dest_id,
                name=d["name"],
                slug=d["slug"],
                country=d["country"],
                state_province_region=d["state"],
                city=d["city"],
                description=f"Explore the beautiful {d['name']}, known for its amazing culture and landscapes. A perfect destination for travelers.",
                short_description=f"Beautiful destination in {d['country']}",
                latitude=d["lat"],
                longitude=d["lon"],
                timezone=d["tz"],
                hero_image_url=get_demo_image_url(f"hero-{d['slug']}"),
                is_active=True
            )
            session.add(existing)
            
        seeded[d["slug"]] = existing
        
    await session.commit()
    logger.info(f"Seeded {len(seeded)} destinations.")
    return seeded

async def clean_demo_destinations(session: AsyncSession) -> int:
    """Delete all destinations starting with 'demo-'."""
    stmt = delete(Destination).where(Destination.slug.like("demo-%"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo destinations.")
    return deleted_count
