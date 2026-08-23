import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.modules.users.models import User, UserRole, Role
from .utils import generate_deterministic_uuid, get_demo_avatar_url

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_TRAVELERS = [
    {"first": "Alice", "last": "Smith", "type": "solo traveler"},
    {"first": "Bob", "last": "Jones", "type": "budget traveler"},
    {"first": "Charlie", "last": "Brown", "type": "luxury traveler"},
    {"first": "Diana", "last": "Prince", "type": "adventure traveler"},
    {"first": "Evan", "last": "Wright", "type": "cultural traveler"},
    {"first": "Fiona", "last": "Gallagher", "type": "digital nomad"},
    {"first": "George", "last": "Miller", "type": "wellness traveler"},
    {"first": "Hannah", "last": "Abbott", "type": "family"},
    {"first": "Ian", "last": "Malcolm", "type": "group traveler"},
    {"first": "Julia", "last": "Roberts", "type": "couple"},
]

DEMO_PROVIDERS = [
    {"first": "Hotel", "last": "Operator", "role": Role.HOST},
    {"first": "Homestay", "last": "Host", "role": Role.HOST},
    {"first": "Resort", "last": "Manager", "role": Role.HOST},
    {"first": "Local", "last": "Guide", "role": Role.GUIDE},
    {"first": "Trekking", "last": "Company", "role": Role.EXPERIENCE_PROVIDER},
    {"first": "Cultural", "last": "Experience", "role": Role.EXPERIENCE_PROVIDER},
    {"first": "Food", "last": "Experience", "role": Role.EXPERIENCE_PROVIDER},
    {"first": "Photography", "last": "Guide", "role": Role.GUIDE},
    {"first": "Wellness", "last": "Provider", "role": Role.SERVICE_PROVIDER},
    {"first": "Adventure", "last": "Provider", "role": Role.EXPERIENCE_PROVIDER},
]

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def seed_users(session: AsyncSession) -> dict[str, list[User]]:
    """Seed demo travelers and providers idempotently."""
    
    seeded_travelers = []
    seeded_providers = []
    
    # 1. Travelers
    for i, t in enumerate(DEMO_TRAVELERS):
        email = f"demo.traveler.{i+1:03d}@demo.itvaya.com"
        username = f"demo_traveler_{i+1:03d}"
        
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            user_id = generate_deterministic_uuid("user", email)
            user = User(
                id=user_id,
                email=email,
                username=username,
                first_name=t["first"],
                last_name=t["last"],
                password_hash=get_password_hash("password123"),
                profile_image_url=get_demo_avatar_url(email),
                is_verified=True,
                is_active=True
            )
            session.add(user)
            
            # Add role
            role_id = generate_deterministic_uuid("user_role", f"{user_id}:traveler")
            role = UserRole(id=role_id, user_id=user_id, role=Role.TRAVELER)
            session.add(role)
            
        seeded_travelers.append(user)
        
    # 2. Providers
    for i, p in enumerate(DEMO_PROVIDERS):
        email = f"demo.provider.{i+1:03d}@demo.itvaya.com"
        username = f"demo_provider_{i+1:03d}"
        
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            user_id = generate_deterministic_uuid("user", email)
            user = User(
                id=user_id,
                email=email,
                username=username,
                first_name=p["first"],
                last_name=p["last"],
                password_hash=get_password_hash("password123"),
                profile_image_url=get_demo_avatar_url(email),
                is_verified=True,
                is_active=True
            )
            session.add(user)
            
            # Add role
            role_id = generate_deterministic_uuid("user_role", f"{user_id}:{p['role'].value}")
            role = UserRole(id=role_id, user_id=user_id, role=p["role"])
            session.add(role)
            
        seeded_providers.append(user)

    await session.commit()
    logger.info(f"Seeded {len(seeded_travelers)} travelers and {len(seeded_providers)} providers.")
    
    return {
        "travelers": seeded_travelers,
        "providers": seeded_providers
    }

async def clean_demo_users(session: AsyncSession) -> int:
    """Delete all users created by the seed script (identified by demo.itvaya.com)."""
    # Delete cascade should handle UserRole
    stmt = delete(User).where(User.email.like("%@demo.itvaya.com"))
    result = await session.execute(stmt)
    await session.commit()
    deleted_count = result.rowcount
    logger.info(f"Cleaned {deleted_count} demo users.")
    return deleted_count
