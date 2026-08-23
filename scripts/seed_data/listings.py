import logging
import random
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.listings.models import (
    Listing, ListingImage, ListingAvailability, PropertyType, ListingStatus, VerificationStatus, Amenity, ListingAmenity
)
from app.modules.users.models import User
from app.modules.destinations.models import Destination
from .utils import generate_deterministic_uuid, get_demo_image_url

logger = logging.getLogger(__name__)

LISTING_TYPES = [
    (PropertyType.HOTEL, "Luxury Hotel", 4000, 15000),
    (PropertyType.HOSTEL, "Backpacker Hostel", 500, 1500),
    (PropertyType.HOMESTAY, "Cozy Homestay", 1500, 4000),
    (PropertyType.APARTMENT, "City Apartment", 3000, 8000),
    (PropertyType.VILLA, "Private Villa", 10000, 30000),
    (PropertyType.RESORT, "Beach Resort", 8000, 25000),
]

async def seed_listings(session: AsyncSession, providers: list[User], destinations: dict[str, Destination]) -> list[Listing]:
    """Seed demo listings idempotently."""
    
    seeded_listings = []
    
    # Get all amenities
    amenities_result = await session.execute(select(Amenity))
    all_amenities = amenities_result.scalars().all()
    
    dest_list = list(destinations.values())
    
    count = 0
    # Let's create about 50 listings (5 per provider on average)
    for i in range(50):
        slug = f"demo-listing-{i+1:03d}"
        
        result = await session.execute(select(Listing).where(Listing.slug == slug))
        existing = result.scalars().first()
        
        if not existing:
            # Deterministically pick data based on index
            provider = providers[i % len(providers)]
            dest = dest_list[(i * 3) % len(dest_list)]
            ptype, ptype_name, min_p, max_p = LISTING_TYPES[i % len(LISTING_TYPES)]
            
            listing_id = generate_deterministic_uuid("listing", slug)
            
            beds = (i % 4) + 1
            capacity = beds * 2
            price = Decimal(str(min_p + ((max_p - min_p) * ((i % 10) / 10))))
            
            existing = Listing(
                id=listing_id,
                host_id=provider.id,
                destination_id=dest.id,
                title=f"{ptype_name} in {dest.name} {i+1}",
                slug=slug,
                description=f"Experience a wonderful stay at this {ptype_name.lower()} located in the heart of {dest.name}. Perfect for travelers looking for comfort and convenience.",
                property_type=ptype,
                guest_capacity=capacity,
                bedrooms=beds,
                beds=beds,
                bathrooms=max(1.0, beds / 2.0),
                address=f"{i+1} Demo Street, {dest.city}, {dest.country}",
                latitude=dest.latitude + (0.01 * (i % 5)),
                longitude=dest.longitude + (0.01 * (i % 5)),
                status=ListingStatus.PUBLISHED,
                verification_status=VerificationStatus.VERIFIED
            )
            session.add(existing)
            
            # Images
            for img_idx in range(3):
                img_id = generate_deterministic_uuid("listing_image", f"{slug}-{img_idx}")
                img = ListingImage(
                    id=img_id,
                    listing_id=listing_id,
                    url=get_demo_image_url(f"{slug}-{img_idx}", category="interior"),
                    is_primary=(img_idx == 0),
                    display_order=img_idx
                )
                session.add(img)
                
            # Amenities
            selected_amenities = all_amenities[0: (i % len(all_amenities)) + 3]
            for am in selected_amenities:
                la_id = generate_deterministic_uuid("listing_amenity", f"{slug}-{am.id}")
                la = ListingAmenity(id=la_id, listing_id=listing_id, amenity_id=am.id)
                session.add(la)
                
            # Availability (next 180 days)
            today = date.today()
            for day_offset in range(180):
                d = today + timedelta(days=day_offset)
                
                # Make some dates unavailable deterministically (e.g., every 10th day)
                is_avail = (i + day_offset) % 10 != 0
                
                avail_id = generate_deterministic_uuid("listing_availability", f"{slug}-{d.isoformat()}")
                avail = ListingAvailability(
                    id=avail_id,
                    listing_id=listing_id,
                    date=d,
                    price=price if is_avail else Decimal('0.00'),
                    is_available=is_avail
                )
                session.add(avail)
                
            count += 1
            
        seeded_listings.append(existing)
        
    await session.commit()
    logger.info(f"Seeded {count} listings with images, amenities, and availability.")
    return seeded_listings


async def clean_demo_listings(session: AsyncSession) -> int:
    """Delete all listings starting with 'demo-'."""
    stmt = delete(Listing).where(Listing.slug.like("demo-%"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo listings.")
    return deleted_count
