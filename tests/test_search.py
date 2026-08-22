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
async def setup_search_data(
    db_session: AsyncSession,
) -> tuple[Destination, Destination]:
    user = User(
        email=f"searchhost_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash="hash",
        username=f"searchhost_{uuid.uuid4().hex[:8]}",
        first_name="Host",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()

    dest1 = Destination(name="Bali", slug=f"bali-{uuid.uuid4().hex[:8]}", country="ID")
    dest2 = Destination(
        name="Tokyo", slug=f"tokyo-{uuid.uuid4().hex[:8]}", country="JP"
    )
    db_session.add_all([dest1, dest2])
    await db_session.flush()

    listing1 = Listing(
        host_id=user.id,
        destination_id=dest1.id,
        title="Beautiful Bali Villa",
        description="A great villa in Bali",
        slug=f"bali-villa-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.VILLA,
        status=ListingStatus.PUBLISHED,
    )
    listing2 = Listing(
        host_id=user.id,
        destination_id=dest2.id,
        title="Tokyo Apartment",
        description="A nice apartment in Tokyo",
        slug=f"tokyo-apt-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.APARTMENT,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add_all([listing1, listing2])

    exp1 = Experience(
        provider_id=user.id,
        destination_id=dest1.id,
        title="Bali Cooking Class",
        description="Learn to cook Bali food",
        slug=f"bali-cooking-{uuid.uuid4().hex[:8]}",
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
        slug=f"tokyo-sushi-{uuid.uuid4().hex[:8]}",
        duration_minutes=120,
        guest_capacity=5,
        base_price=Decimal("150.00"),
        status=ExperienceStatus.PUBLISHED,
    )
    db_session.add_all([exp1, exp2])

    await db_session.commit()
    return dest1, dest2


async def test_keyword_search(async_client: AsyncClient, setup_search_data):
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search", params={"query": "Sushi"}
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) > 0
    assert any("Sushi" in r["data"]["title"] for r in results)


async def test_destination_filter(async_client: AsyncClient, setup_search_data):
    dest1, dest2 = setup_search_data
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search", params={"destination_id": str(dest1.id)}
    )
    assert res.status_code == 200
    results = res.json()["results"]
    # Should only return Bali items
    assert len(results) >= 2
    for r in results:
        assert r["data"]["destination_id"] == str(dest1.id)


async def test_price_filter(async_client: AsyncClient, setup_search_data):
    # Search experiences for price filter
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search",
        params={"type": "experience", "min_price": 100},
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) > 0
    for r in results:
        assert float(r["data"]["base_price"]) >= 100


async def test_pagination(async_client: AsyncClient, setup_search_data):
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search", params={"limit": 1}
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) <= 2  # limit 1 per type = max 2


async def test_sorting(async_client: AsyncClient, setup_search_data):
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search",
        params={"type": "experience", "sort_by": "price_desc"},
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) >= 2
    assert float(results[0]["data"]["base_price"]) >= float(
        results[1]["data"]["base_price"]
    )


async def test_empty_results(async_client: AsyncClient, setup_search_data):
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search", params={"query": "nonexistentxyz123"}
    )
    assert res.status_code == 200
    assert res.json()["total_count"] == 0


async def test_invalid_parameters(async_client: AsyncClient, setup_search_data):
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search", params={"limit": -5}
    )
    assert res.status_code == 422
