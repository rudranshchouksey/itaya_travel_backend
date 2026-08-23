import logging
from datetime import date, timedelta, time
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.experiences.models import (
    Experience, ExperienceImage, ExperienceAvailability, ExperienceCategory,
    ExperienceCategoryLink, ExperienceStatus, ExperienceVerificationStatus
)
from app.modules.users.models import User
from app.modules.destinations.models import Destination
from .utils import generate_deterministic_uuid, get_demo_image_url

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("adventure", "Adventure"),
    ("food", "Food & Drink"),
    ("culture", "Culture & History"),
    ("wellness", "Wellness"),
    ("photography", "Photography"),
    ("trekking", "Trekking"),
    ("nightlife", "Nightlife"),
    ("sightseeing", "Sightseeing"),
]

EXPERIENCE_TEMPLATES = [
    ("City Walking Tour", 120, 15, 500, "culture"),
    ("Mountain Trek", 360, 8, 2500, "trekking"),
    ("Local Food Tasting", 180, 10, 1200, "food"),
    ("Sunset Photography", 150, 5, 800, "photography"),
    ("Yoga Retreat Day", 240, 20, 1500, "wellness"),
    ("Scuba Diving", 240, 4, 4500, "adventure"),
]

async def seed_experiences(session: AsyncSession, providers: list[User], destinations: dict[str, Destination]) -> list[Experience]:
    """Seed demo experiences idempotently."""
    
    seeded_experiences = []
    
    # 1. Categories
    category_map = {}
    for slug, name in CATEGORIES:
        result = await session.execute(select(ExperienceCategory).where(ExperienceCategory.slug == slug))
        existing_cat = result.scalars().first()
        if not existing_cat:
            cat_id = generate_deterministic_uuid("exp_cat", slug)
            existing_cat = ExperienceCategory(id=cat_id, name=name, slug=slug)
            session.add(existing_cat)
        category_map[slug] = existing_cat
        
    await session.commit()
    
    dest_list = list(destinations.values())
    count = 0
    
    # 2. Experiences
    for i in range(40):
        slug = f"demo-exp-{i+1:03d}"
        
        result = await session.execute(select(Experience).where(Experience.slug == slug))
        existing = result.scalars().first()
        
        if not existing:
            provider = providers[(i * 2) % len(providers)]
            dest = dest_list[(i * 4) % len(dest_list)]
            template_name, duration, cap, price, cat_slug = EXPERIENCE_TEMPLATES[i % len(EXPERIENCE_TEMPLATES)]
            
            exp_id = generate_deterministic_uuid("experience", slug)
            
            existing = Experience(
                id=exp_id,
                provider_id=provider.id,
                destination_id=dest.id,
                title=f"{template_name} in {dest.name} {i+1}",
                slug=slug,
                description=f"Join us for an amazing {template_name.lower()} in the beautiful city of {dest.name}. Unforgettable memories guaranteed.",
                duration_minutes=duration,
                guest_capacity=cap,
                base_price=Decimal(str(price)),
                currency="INR", # Aligning with global defaults
                meeting_point=f"Central Square, {dest.city}",
                status=ExperienceStatus.PUBLISHED,
                verification_status=ExperienceVerificationStatus.VERIFIED
            )
            session.add(existing)
            
            # Category link
            cat = category_map[cat_slug]
            link_id = generate_deterministic_uuid("exp_cat_link", f"{slug}-{cat.slug}")
            link = ExperienceCategoryLink(id=link_id, experience_id=exp_id, category_id=cat.id)
            session.add(link)
            
            # Images
            for img_idx in range(2):
                img_id = generate_deterministic_uuid("exp_image", f"{slug}-{img_idx}")
                img = ExperienceImage(
                    id=img_id,
                    experience_id=exp_id,
                    url=get_demo_image_url(f"{slug}-{img_idx}", category="nature"),
                    is_primary=(img_idx == 0),
                    display_order=img_idx
                )
                session.add(img)
                
            # Availability (next 90 days, weekends only for some, daily for others)
            today = date.today()
            for day_offset in range(90):
                d = today + timedelta(days=day_offset)
                
                # e.g., Every 3rd day
                is_avail = (i + day_offset) % 3 == 0
                
                if is_avail:
                    avail_id = generate_deterministic_uuid("exp_availability", f"{slug}-{d.isoformat()}")
                    avail = ExperienceAvailability(
                        id=avail_id,
                        experience_id=exp_id,
                        date=d,
                        start_time=time(9, 0),
                        end_time=time(9 + (duration // 60), (duration % 60)),
                        price_override=None,
                        is_available=True
                    )
                    session.add(avail)
                    
            count += 1
            
        seeded_experiences.append(existing)
        
    await session.commit()
    logger.info(f"Seeded {count} experiences with images, categories, and availability.")
    return seeded_experiences


async def clean_demo_experiences(session: AsyncSession) -> int:
    """Delete all experiences starting with 'demo-'."""
    stmt = delete(Experience).where(Experience.slug.like("demo-%"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo experiences.")
    return deleted_count
