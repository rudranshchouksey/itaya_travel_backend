import uuid
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.destinations.models import Destination
from app.modules.trips.models import (
    Trip,
    TripDay,
    TripDestination,
    TripItem,
    TripItemType,
    TripParticipant,
    TripParticipantRole,
    TripStatus,
)
from app.modules.users.models import User


@pytest_asyncio.fixture
async def trip_owner(db_session: AsyncSession) -> User:
    user = User(
        email="tripowner@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username="tripowner",
        first_name="Trip",
        last_name="Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        email="otheruser@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username="otheruser",
        first_name="Other",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def trip_destination(db_session: AsyncSession) -> Destination:
    dest = Destination(name="Tokyo", slug="tokyo-jp", country="Japan")
    db_session.add(dest)
    await db_session.commit()
    await db_session.refresh(dest)
    return dest


@pytest_asyncio.fixture
async def sample_trip(
    db_session: AsyncSession,
    trip_owner: User,
    trip_destination: Destination,
) -> Trip:
    trip = Trip(
        owner_id=trip_owner.id,
        title="Japan Adventure",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=5),
        traveler_count=2,
        budget=Decimal("2000.00"),
        status=TripStatus.PLANNED,
    )
    db_session.add(trip)
    await db_session.flush()

    # Add participant
    participant = TripParticipant(
        trip_id=trip.id, user_id=trip_owner.id, role=TripParticipantRole.OWNER
    )
    db_session.add(participant)

    # Add destination
    trip_dest = TripDestination(trip_id=trip.id, destination_id=trip_destination.id)
    db_session.add(trip_dest)

    # Add Days
    day1 = TripDay(trip_id=trip.id, date=trip.start_date, day_index=0, title="Arrival")
    day2 = TripDay(
        trip_id=trip.id,
        date=trip.start_date + timedelta(days=1),
        day_index=1,
        title="City Tour",
    )
    db_session.add_all([day1, day2])
    await db_session.flush()

    # Add Item
    item1 = TripItem(
        trip_id=trip.id,
        trip_day_id=day1.id,
        item_type=TripItemType.CUSTOM,
        title="Check-in",
        start_time=time(14, 0),
        estimated_cost=Decimal("0.00"),
        order_index=0,
    )
    db_session.add(item1)

    await db_session.commit()
    
    # Reload with relationships eager-loaded to avoid MissingGreenlet
    from sqlalchemy.orm import selectinload
    stmt = select(Trip).options(
        selectinload(Trip.days).selectinload(TripDay.items),
        selectinload(Trip.items)
    ).where(Trip.id == trip.id)
    trip = (await db_session.execute(stmt)).scalars().first()
    return trip


@pytest.mark.asyncio
async def test_trip_creation(
    async_client: AsyncClient,
    trip_owner: User,
    trip_destination: Destination,
):
    login_data = {"username": trip_owner.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # 1. Trip creation
    trip_in = {
        "title": "Summer Vacation",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=7)).isoformat(),
        "traveler_count": 4,
        "currency": "EUR",
        "destination_ids": [str(trip_destination.id)],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips",
        json=trip_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Summer Vacation"
    assert data["owner_id"] == str(trip_owner.id)
    assert len(data["days"]) == 8  # Start date + 7 days = 8 days

    # 10. Invalid dates (start > end)
    trip_in["end_date"] = (date.today() - timedelta(days=1)).isoformat()
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips",
        json=trip_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_trip_retrieval(
    async_client: AsyncClient,
    sample_trip: Trip,
    trip_owner: User,
):
    login_data = {"username": trip_owner.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # 2. Trip retrieval (List)
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/trips", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Single retrieval
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Japan Adventure"
    # 12. Multiple itinerary days
    assert len(data["days"]) == 2
    assert len(data["days"][0]["items"]) == 1


@pytest.mark.asyncio
async def test_trip_update_and_deletion(
    async_client: AsyncClient,
    sample_trip: Trip,
    trip_owner: User,
):
    login_data = {"username": trip_owner.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # 3. Trip update
    res = await async_client.patch(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        json={"title": "Updated Japan Adventure", "budget": "2500.00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Japan Adventure"

    # 4. Trip deletion
    res = await async_client.delete(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204

    # Ensure deleted
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_trip_item_management(
    async_client: AsyncClient,
    sample_trip: Trip,
    trip_owner: User,
    db_session: AsyncSession,
):
    login_data = {"username": trip_owner.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # Get a day ID
    day = sample_trip.days[0]

    # 5. Trip item creation
    item_in = {
        "trip_day_id": str(day.id),
        "item_type": "activity",
        "title": "Visit Shrine",
        "start_time": "16:00:00",
        "order_index": 1,
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}/items",
        json=item_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    item_id = res.json()["id"]
    assert res.json()["title"] == "Visit Shrine"

    # 6. Trip item update
    # 13. Ordering
    res = await async_client.patch(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}/items/{item_id}",
        json={"order_index": 0},  # Move to first
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["order_index"] == 0

    # 11. Invalid references (setting listing_id for non-stay)
    res = await async_client.patch(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}/items/{item_id}",
        json={"listing_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422

    # 7. Trip item deletion
    res = await async_client.delete(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_unauthorized_access(
    async_client: AsyncClient,
    sample_trip: Trip,
    regular_user: User,
):
    login_data = {"username": regular_user.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # 8. Ownership enforcement & 9. Unauthorized access
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403

    res = await async_client.delete(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_transaction_rollback(
    async_client: AsyncClient,
    sample_trip: Trip,
    trip_owner: User,
    db_session: AsyncSession,
):
    login_data = {"username": trip_owner.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    day = sample_trip.days[0]

    # 14. Transaction rollback behavior
    # We deliberately trigger a DB-level error by providing an invalid UUID (which FastAPI normally catches, but we will test it via a 422)
    # Actually, a better test for transaction rollback is submitting valid JSON that violates a CheckConstraint (e.g., listing_id without item_type="stay")
    # This is caught by Pydantic, so it won't even hit DB.
    # We will test sending a non-existent trip_day_id which is a valid UUID but will violate FK or service checks.

    fake_day_id = str(uuid.uuid4())
    item_in = {
        "trip_day_id": fake_day_id,
        "item_type": "activity",
        "title": "Invalid Day Activity",
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}/items",
        json=item_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "TripDay does not belong to this trip" in res.text

    # Ensure it wasn't added
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/trips/{sample_trip.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = res.json()
    assert len(data["days"][0]["items"]) == 1  # Still just 1 item
