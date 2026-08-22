import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.bookings.models import (
    Booking,
    BookingItem,
    BookingStatus,
    TripItemType,
)
from app.modules.destinations.models import Destination
from app.modules.listings.models import (
    Listing,
    ListingAvailability,
    ListingStatus,
    PropertyType,
    VerificationStatus,
)
from app.modules.users.models import User


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="testuser@example.com",
        username="testuser",
        password_hash=get_password_hash("StrongPassword123!"),
        first_name="Test",
        last_name="User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_token(async_client: AsyncClient, test_user: User) -> str:
    login_data = {"username": "testuser@example.com", "password": "StrongPassword123!"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_journey_1_anonymous_discovery(
    async_client: AsyncClient, db_session: AsyncSession
):
    # Setup some basic data
    dest = Destination(
        name="Journey Destination",
        slug="journey-dest",
        country="Test Country",
        description="A great place",
        is_active=True,
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=uuid.uuid4(),  # Using random for host since we don't need real user for anon browsing
        destination_id=dest.id,
        title="Journey Listing",
        slug="journey-listing",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
        verification_status=VerificationStatus.VERIFIED,
    )
    db_session.add(listing)
    await db_session.commit()

    # 1. Search listing
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/search", params={"query": "Journey"}
    )
    assert res.status_code == 200
    results = res.json()["results"]
    listings = [r for r in results if r["item_type"] == "listing"]
    assert len(listings) > 0
    dest_id = listings[0]["data"]["destination_id"]
    dest_slug = dest.slug  # we already have dest

    # 2. View destination
    res = await async_client.get(f"{settings.API_V1_PREFIX}/destinations/{dest_slug}")
    assert res.status_code == 200

    # 3. Search listing in destination
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings", params={"destination_id": dest_id}
    )
    assert res.status_code == 200
    listings = res.json()
    assert len(listings) > 0
    listing_slug = listings[0]["slug"]

    # 4. View listing
    res = await async_client.get(f"{settings.API_V1_PREFIX}/listings/{listing_slug}")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_journey_2_authenticated_trip_builder(
    async_client: AsyncClient, db_session: AsyncSession
):
    # 1. Register
    register_data = {
        "email": "journey2@example.com",
        "username": "journey2",
        "password": "StrongPassword123!",
        "first_name": "Journey",
        "last_name": "Two",
    }
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register", json=register_data
    )
    assert res.status_code == 201

    # 2. Login
    login_data = {"username": "journey2@example.com", "password": "StrongPassword123!"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    start_d = date.today()
    end_d = start_d + timedelta(days=5)

    # 3. Create trip
    trip_data = {
        "title": "My Test Trip",
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "traveler_count": 2,
        "currency": "USD",
    }
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips", json=trip_data, headers=headers
    )
    assert res.status_code == 201
    trip_id = res.json()["id"]
    day_id = res.json()["days"][0]["id"]

    # 4. Add stay
    stay_item = {"item_type": "custom", "title": "Random Hotel", "trip_day_id": day_id}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips/{trip_id}/items",
        json=stay_item,
        headers=headers,
    )
    assert res.status_code == 201

    # 5. Add experience
    exp_item = {"item_type": "custom", "title": "Random Tour", "trip_day_id": day_id}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/trips/{trip_id}/items",
        json=exp_item,
        headers=headers,
    )
    assert res.status_code == 201

    # 6. Update trip
    res = await async_client.patch(
        f"{settings.API_V1_PREFIX}/trips/{trip_id}",
        json={"budget": 1500.00},
        headers=headers,
    )
    assert res.status_code == 200
    assert float(res.json()["budget"]) == 1500.0


@pytest.mark.asyncio
async def test_journey_3_booking_and_payment_flow(
    async_client: AsyncClient,
    test_user_token: str,
    test_user: User,
    db_session: AsyncSession,
):
    # Setup listing
    listing = Listing(
        host_id=test_user.id,
        destination_id=uuid.uuid4(),
        title="Booking Listing",
        slug="booking-listing",
        property_type=PropertyType.HOTEL,
        guest_capacity=4,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {test_user_token}"}
    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    for i in range(5):
        avail = ListingAvailability(
            listing_id=listing.id,
            date=start_d + timedelta(days=i),
            price=Decimal("200.00"),
            is_available=True,
        )
        db_session.add(avail)
    await db_session.commit()

    # 1. Search availability
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings/{listing.id}/availability",
        params={"start_date": start_d.isoformat(), "end_date": end_d.isoformat()},
    )
    assert res.status_code == 200

    # 2. Create booking
    booking_req = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing.id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "Test", "last_name": "User", "is_primary": True}],
    }
    headers = {
        "Authorization": f"Bearer {test_user_token}",
        "X-Payment-Token": "success_token",
    }
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_req, headers=headers
    )
    assert res.status_code == 201
    booking_id = res.json()["id"]

    # 4. Retrieve booking
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}", headers=headers
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_journey_4_review_flow(
    async_client: AsyncClient,
    test_user_token: str,
    test_user: User,
    db_session: AsyncSession,
):
    # Setup completed booking
    listing = Listing(
        host_id=test_user.id,
        destination_id=uuid.uuid4(),
        title="Review Listing",
        slug="review-listing",
        property_type=PropertyType.HOTEL,
        guest_capacity=4,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    booking = Booking(
        user_id=test_user.id,
        reference="REV-123",
        booking_status=BookingStatus.COMPLETED,
        subtotal=Decimal("200.00"),
        total=Decimal("200.00"),
        currency="USD",
    )
    db_session.add(booking)
    await db_session.flush()

    item = BookingItem(
        booking_id=booking.id,
        item_type=TripItemType.STAY,
        listing_id=listing.id,
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() - timedelta(days=4),
        price_snapshot=Decimal("200.00"),
        subtotal=Decimal("200.00"),
    )
    db_session.add(item)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {test_user_token}"}

    # 1. Submit review
    review_data = {
        "booking_item_id": str(item.id),
        "rating": 5,
        "title": "Great Review Journey",
        "body": "Loved it.",
    }
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers
    )
    assert res.status_code == 201

    # 2. Retrieve review
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/listings/{listing.id}/reviews"
    )
    assert res.status_code == 200
    assert len(res.json()) > 0


@pytest.mark.asyncio
async def test_journey_5_ai_assisted_planning(
    async_client: AsyncClient, db_session: AsyncSession
):
    dest = Destination(
        name="AI Destination",
        slug="ai-dest",
        country="AI Country",
        description="A great place",
        is_active=True,
    )
    db_session.add(dest)
    await db_session.commit()

    start_d = date.today()
    end_d = start_d + timedelta(days=2)

    # 1. AI Intent to Proposed Itinerary
    ai_req = {
        "destination_id": str(dest.id),
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "budget": 2000.0,
        "traveler_count": 2,
        "travel_style": "balanced",
        "interests": ["culture", "food"],
        "preferred_accommodation": "hotel",
        "free_form_request": "I want a relaxing trip",
    }
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/ai/trips/plan", json=ai_req
    )
    assert res.status_code == 200
    plan = res.json()
    assert plan["destination_id"] == str(dest.id)
    assert len(plan["days"]) > 0
