import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.destinations.models import Destination
from app.modules.experiences.models import Experience, ExperienceStatus
from app.modules.listings.models import Listing, ListingStatus, PropertyType
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def setup_recommendation_data(db_session: AsyncSession) -> tuple[Destination, Destination]:
    user = User(
        email=f"rechost_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash="hash",
        username=f"rechost_{uuid.uuid4().hex[:8]}",
        first_name="Host",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()

    dest1 = Destination(name="Bali", slug=f"bali-rec-{uuid.uuid4().hex[:8]}", country="ID")
    dest2 = Destination(name="Tokyo", slug=f"tokyo-rec-{uuid.uuid4().hex[:8]}", country="JP")
    db_session.add_all([dest1, dest2])
    await db_session.flush()

    listing1 = Listing(
        host_id=user.id,
        destination_id=dest1.id,
        title="Beautiful Bali Villa",
        description="A great villa in Bali",
        slug=f"bali-villa-rec-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.VILLA,
        status=ListingStatus.PUBLISHED,
    )
    listing2 = Listing(
        host_id=user.id,
        destination_id=dest2.id,
        title="Tokyo Apartment",
        description="A nice apartment in Tokyo",
        slug=f"tokyo-apt-rec-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.APARTMENT,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add_all([listing1, listing2])

    exp1 = Experience(
        provider_id=user.id,
        destination_id=dest1.id,
        title="Bali Cooking Class",
        description="Learn to cook Bali food",
        slug=f"bali-cooking-rec-{uuid.uuid4().hex[:8]}",
        duration_minutes=120,
        guest_capacity=10,
        base_price=Decimal("50.00"),
        status=ExperienceStatus.PUBLISHED,
    )
    exp2 = Experience(
        provider_id=user.id,
        destination_id=dest2.id,
        title="Tokyo Sushi Making",
        description="Learn to make sushi",
        slug=f"tokyo-sushi-rec-{uuid.uuid4().hex[:8]}",
        duration_minutes=120,
        guest_capacity=5,
        base_price=Decimal("150.00"),
        status=ExperienceStatus.PUBLISHED,
    )
    db_session.add_all([exp1, exp2])
    
    await db_session.commit()
    return dest1, dest2


async def test_valid_ranking(async_client: AsyncClient, setup_recommendation_data):
    dest1, dest2 = setup_recommendation_data
    res = await async_client.get(f"{settings.API_V1_PREFIX}/recommendations", params={"destination_id": str(dest1.id)})
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) > 0
    # Items in dest1 should have higher score due to our deterministic logic
    for r in results:
        if r["data"]["destination_id"] == str(dest1.id):
            assert r["score"] > 1.0


async def test_deterministic_ranking(async_client: AsyncClient, setup_recommendation_data):
    dest1, dest2 = setup_recommendation_data
    # Preference for villas
    res = await async_client.get(f"{settings.API_V1_PREFIX}/recommendations", params={"preferred_types": ["villa"]})
    assert res.status_code == 200
    results = res.json()["results"]
    # In deterministic logic, it should filter by property type for listings
    for r in results:
        if r["item_type"] == "listing":
            assert r["data"]["property_type"] == "villa"


async def test_empty_preferences(async_client: AsyncClient, setup_recommendation_data):
    res = await async_client.get(f"{settings.API_V1_PREFIX}/recommendations")
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) > 0
    # All base scores should be 1.0 since no prefs matched
    assert all(r["score"] == 1.0 for r in results)


async def test_invalid_input(async_client: AsyncClient, setup_recommendation_data):
    res = await async_client.get(f"{settings.API_V1_PREFIX}/recommendations", params={"limit": 100}) # > 50
    assert res.status_code == 422
