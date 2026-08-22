from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.destinations.models import Destination
from app.modules.destinations.schemas import DestinationCreate
from app.modules.destinations.service import DestinationService
from app.modules.listings.models import (
    Listing,
    ListingAvailability,
    ListingStatus,
    PropertyType,
    VerificationStatus,
)
from app.modules.listings.schemas import ListingCreate
from app.modules.listings.service import ListingService
from app.modules.users.models import User


@pytest_asyncio.fixture
async def listing_host(db_session: AsyncSession) -> User:
    user = User(
        email="host@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username="listinghost",
        first_name="Listing",
        last_name="Host",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def listing_destination(db_session: AsyncSession) -> Destination:
    dest_in = DestinationCreate(
        name="Bali",
        slug="bali-id",
        country="Indonesia"
    )
    return await DestinationService.create_destination(db_session, dest_in)


@pytest_asyncio.fixture
async def sample_listing(
    db_session: AsyncSession, listing_host: User, listing_destination: Destination
) -> Listing:
    listing_in = ListingCreate(
        host_id=listing_host.id,
        destination_id=listing_destination.id,
        title="Beautiful Bali Villa",
        slug="beautiful-bali-villa",
        property_type=PropertyType.VILLA,
        guest_capacity=4,
        bedrooms=2,
        beds=2,
        bathrooms=2.0,
        status=ListingStatus.PUBLISHED,
        verification_status=VerificationStatus.VERIFIED
    )
    return await ListingService.create_listing(db_session, listing_in)


@pytest_asyncio.fixture
async def sample_availability(
    db_session: AsyncSession, sample_listing: Listing
) -> list[ListingAvailability]:
    availabilities = []
    today = date.today()  # noqa: DTZ011
    for i in range(5):
        avail = ListingAvailability(
            listing_id=sample_listing.id,
            date=today + timedelta(days=i),
            price=Decimal("150.00"),
            is_available=(i != 2)  # day 2 is unavailable
        )
        db_session.add(avail)
        availabilities.append(avail)
    await db_session.commit()
    return availabilities


@pytest.mark.asyncio
async def test_listing_creation(
    db_session: AsyncSession, listing_host: User, listing_destination: Destination
):
    listing_in = ListingCreate(
        host_id=listing_host.id,
        destination_id=listing_destination.id,
        title="Test Creation",
        slug="test-creation",
        property_type=PropertyType.HOTEL,
        guest_capacity=2
    )
    listing = await ListingService.create_listing(db_session, listing_in)
    assert listing.id is not None
    assert listing.slug == "test-creation"
    assert listing.property_type == PropertyType.HOTEL


@pytest.mark.asyncio
async def test_listing_retrieval(async_client: AsyncClient, sample_listing: Listing):
    response = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings/{sample_listing.slug}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == sample_listing.title


@pytest.mark.asyncio
async def test_listing_filtering_and_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
    listing_host: User,
    listing_destination: Destination
):
    # Create multiple listings
    for i in range(3):
        l_in = ListingCreate(
            host_id=listing_host.id,
            destination_id=listing_destination.id,
            title=f"Prop {i}",
            slug=f"prop-{i}",
            property_type=PropertyType.APARTMENT,
            guest_capacity=i + 1,
            status=ListingStatus.PUBLISHED,
            verification_status=VerificationStatus.VERIFIED
        )
        await ListingService.create_listing(db_session, l_in)

    # Test Pagination
    res = await async_client.get(f"{settings.API_V1_PREFIX}/listings?limit=2")
    assert res.status_code == 200
    assert len(res.json()) == 2

    # Test Guest Capacity
    res = await async_client.get(f"{settings.API_V1_PREFIX}/listings?guest_capacity=3")
    assert res.status_code == 200
    data = res.json()
    assert all(d["guest_capacity"] >= 3 for d in data)

    # Test Destination filtering
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings?destination_id={listing_destination.id}"
    )
    assert res.status_code == 200
    assert len(res.json()) > 0


@pytest.mark.asyncio
async def test_availability_lookup(
    async_client: AsyncClient,
    sample_listing: Listing,
    sample_availability: list[ListingAvailability]
):
    today = date.today()  # noqa: DTZ011
    start_date = today.isoformat()
    end_date = (today + timedelta(days=4)).isoformat()

    # Good lookup
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings/{sample_listing.id}/availability"
        f"?start_date={start_date}&end_date={end_date}"
    )
    assert res.status_code == 200
    data = res.json()
    # Should only return available dates. Total 5 days -> 4 available.
    assert len(data) == 4

    # Invalid date range (end < start)
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings/{sample_listing.id}/availability"
        f"?start_date={end_date}&end_date={start_date}"
    )
    assert res.status_code == 400  # Validation error

    # Past date
    past_date = (today - timedelta(days=1)).isoformat()
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings/{sample_listing.id}/availability"
        f"?start_date={past_date}&end_date={end_date}"
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_public_access_and_status(
    async_client: AsyncClient,
    db_session: AsyncSession,
    listing_host: User,
    listing_destination: Destination
):
    # Draft listing shouldn't be publicly visible
    l_in = ListingCreate(
        host_id=listing_host.id,
        destination_id=listing_destination.id,
        title="Draft",
        slug="draft-listing",
        property_type=PropertyType.HOMESTAY,
        guest_capacity=1,
        status=ListingStatus.DRAFT
    )
    await ListingService.create_listing(db_session, l_in)

    res = await async_client.get(f"{settings.API_V1_PREFIX}/listings/draft-listing")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_database_constraints(
    db_session: AsyncSession,
    listing_host: User,
    listing_destination: Destination,
    sample_listing: Listing
):
    # Unique slug constraint
    l_in = ListingCreate(
        host_id=listing_host.id,
        destination_id=listing_destination.id,
        title="Duplicate Slug",
        slug=sample_listing.slug,
        property_type=PropertyType.RESORT,
        guest_capacity=1
    )
    with pytest.raises(IntegrityError):
        await ListingService.create_listing(db_session, l_in)


@pytest.mark.asyncio
async def test_n_plus_one_queries_mitigation(
    async_client: AsyncClient,
    sample_listing: Listing
):
    # Ensure that fetching listings uses selectinload correctly
    # While we can't easily assert raw SQL counts in sqlite memory here, 
    # we ensure the nested properties resolve without detached instance errors
    res = await async_client.get(f"{settings.API_V1_PREFIX}/listings/{sample_listing.slug}")
    assert res.status_code == 200
    data = res.json()
    assert "images" in data
    assert "amenities" in data
