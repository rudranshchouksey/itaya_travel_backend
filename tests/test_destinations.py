import pytest
import pytest_asyncio
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.destinations.models import Destination
from app.modules.destinations.schemas import DestinationCreate
from app.modules.destinations.service import DestinationService


@pytest_asyncio.fixture
async def sample_destination(db_session: AsyncSession) -> Destination:
    dest_in = DestinationCreate(
        name="Paris",
        slug="paris-france",
        country="France",
        state_province_region="Île-de-France",
        city="Paris",
        description="The City of Light",
        short_description="Capital of France",
        latitude=48.8566,
        longitude=2.3522,
        timezone="Europe/Paris",
        is_active=True,
    )
    return await DestinationService.create_destination(db_session, dest_in)


@pytest_asyncio.fixture
async def multi_destinations(db_session: AsyncSession) -> list[Destination]:
    dests = []
    dest_data = [
        {"name": "Tokyo", "slug": "tokyo-japan", "country": "Japan"},
        {"name": "Kyoto", "slug": "kyoto-japan", "country": "Japan"},
        {"name": "Osaka", "slug": "osaka-japan", "country": "Japan"},
        {"name": "New York", "slug": "new-york-us", "country": "United States"},
        {"name": "London", "slug": "london-uk", "country": "United Kingdom"},
    ]
    for data in dest_data:
        dest_in = DestinationCreate(**data)
        dest = await DestinationService.create_destination(db_session, dest_in)
        dests.append(dest)
    return dests


@pytest.mark.asyncio
async def test_create_destination_service(db_session: AsyncSession):
    dest_in = DestinationCreate(
        name="Rome",
        slug="rome-italy",
        country="Italy",
        latitude=41.9028,
        longitude=12.4964,
    )
    dest = await DestinationService.create_destination(db_session, dest_in)
    assert dest.id is not None
    assert dest.name == "Rome"
    assert dest.slug == "rome-italy"


@pytest.mark.asyncio
async def test_list_destinations_public(
    async_client: AsyncClient, multi_destinations: list[Destination]
):
    response = await async_client.get(f"{settings.API_V1_PREFIX}/destinations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
    # Should be sorted by name by default: Kyoto, London, New York, Osaka, Tokyo
    assert data[0]["name"] == "Kyoto"


@pytest.mark.asyncio
async def test_list_destinations_pagination(
    async_client: AsyncClient, multi_destinations: list[Destination]
):
    response = await async_client.get(
        f"{settings.API_V1_PREFIX}/destinations?skip=1&limit=2"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Sorted by name: Kyoto, London, New York, Osaka, Tokyo
    # Skip 1 -> London, New York
    assert data[0]["name"] == "London"
    assert data[1]["name"] == "New York"


@pytest.mark.asyncio
async def test_search_destinations(
    async_client: AsyncClient, multi_destinations: list[Destination]
):
    response = await async_client.get(
        f"{settings.API_V1_PREFIX}/destinations?search=yo"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # Kyoto, New York, Tokyo
    names = [d["name"] for d in data]
    assert "Kyoto" in names
    assert "New York" in names
    assert "Tokyo" in names


@pytest.mark.asyncio
async def test_get_destination_by_slug(
    async_client: AsyncClient, sample_destination: Destination
):
    response = await async_client.get(
        f"{settings.API_V1_PREFIX}/destinations/{sample_destination.slug}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Paris"
    assert data["latitude"] == 48.8566

    # Also test summary endpoint
    summary_response = await async_client.get(
        f"{settings.API_V1_PREFIX}/destinations/{sample_destination.slug}/summary"
    )
    assert summary_response.status_code == 200
    summary_data = summary_response.json()
    assert summary_data["name"] == "Paris"
    assert "latitude" not in summary_data  # Should be lightweight


@pytest.mark.asyncio
async def test_get_unknown_slug(async_client: AsyncClient):
    response = await async_client.get(
        f"{settings.API_V1_PREFIX}/destinations/unknown-place"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Destination not found"


@pytest.mark.asyncio
async def test_duplicate_slug_constraint(
    db_session: AsyncSession, sample_destination: Destination
):
    # Try to create another destination with the same slug
    dest_in = DestinationCreate(
        name="Paris Duplicate", slug="paris-france", country="France"
    )
    with pytest.raises(IntegrityError):
        await DestinationService.create_destination(db_session, dest_in)


def test_invalid_coordinates_validation():
    with pytest.raises(ValidationError):
        DestinationCreate(
            name="Nowhere",
            slug="nowhere",
            country="Null Island",
            latitude=91.0,  # Invalid
            longitude=0.0,
        )

    with pytest.raises(ValidationError):
        DestinationCreate(
            name="Nowhere",
            slug="nowhere",
            country="Null Island",
            latitude=0.0,
            longitude=-181.0,  # Invalid
        )


def test_invalid_slug_validation():
    with pytest.raises(ValidationError):
        DestinationCreate(
            name="Bad Slug",
            slug="bad_slug",  # Underscores not allowed
            country="Test",
        )
    with pytest.raises(ValidationError):
        DestinationCreate(name="Bad Slug 2", slug="-leading-dash", country="Test")
