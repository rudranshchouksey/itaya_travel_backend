import asyncio
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.bookings.models import BookingStatus, PaymentStatus
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"bookinguser_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"bookinguser_{uuid.uuid4().hex[:8]}",
        first_name="Booking",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_token(async_client: AsyncClient, test_user: User) -> str:
    login_data = {"username": test_user.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    return res.json()["access_token"]


from app.modules.destinations.models import Destination
from app.modules.experiences.models import (
    Experience,
    ExperienceAvailability,
    ExperienceStatus,
)
from app.modules.listings.models import (
    Listing,
    ListingAvailability,
    ListingStatus,
    PropertyType,
)


async def setup_test_data(db_session: AsyncSession, host_user: User) -> tuple[uuid.UUID, uuid.UUID]:
    # 1. Create a destination
    dest = Destination(name="Booking Dest", slug=f"booking-dest-{uuid.uuid4().hex[:8]}", country="TC")
    db_session.add(dest)
    await db_session.flush()

    # 2. Create a listing
    listing = Listing(
        host_id=host_user.id,
        destination_id=dest.id,
        title="Booking Listing",
        slug=f"booking-listing-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=4,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    # 3. Add availability to listing
    start_d = date.today() + timedelta(days=10)
    for i in range(5):
        avail = ListingAvailability(
            listing_id=listing.id,
            date=start_d + timedelta(days=i),
            price=Decimal("100.00"),
            is_available=True,
        )
        db_session.add(avail)

    # 4. Create an experience
    exp = Experience(
        provider_id=host_user.id,
        destination_id=dest.id,
        title="Booking Experience",
        slug=f"booking-exp-{uuid.uuid4().hex[:8]}",
        duration_minutes=120,
        guest_capacity=10,
        base_price=Decimal("50.00"),
        currency="USD",
        status=ExperienceStatus.PUBLISHED,
    )
    db_session.add(exp)
    await db_session.flush()

    # 5. Add availability to experience
    exp_avail = ExperienceAvailability(
        experience_id=exp.id,
        date=start_d,
        start_time=time(10, 0),
        end_time=time(12, 0),
        price_override=Decimal("60.00"),
        is_available=True,
    )
    db_session.add(exp_avail)

    await db_session.commit()
    return listing.id, exp.id


async def test_successful_booking_and_payment_success(
    async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User
):
    # Tests criteria 1 & 13
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [
            {
                "first_name": "Test",
                "last_name": "User",
                "is_primary": True,
            }
        ],
    }

    # Use payment mock success token
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json=booking_data,
        headers={**headers, "X-Payment-Token": "success_token"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["booking_status"] == BookingStatus.CONFIRMED
    assert data["payment_status"] == PaymentStatus.AUTHORIZED
    assert data["total"] == "200.00"  # 2 days * 100


async def test_unavailable_listing(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Book once
    await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )

    # Book again for same dates
    res2 = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res2.status_code == 422
    assert "not available" in res2.json()["error"]["message"].lower()


async def test_invalid_dates(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": "2026-10-12",
                "end_date": "2026-10-10", # Invalid!
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 422


async def test_invalid_guest_count(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 10, # Exceeds capacity 4
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 422


async def test_idempotent_request(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    headers_with_idempotency = {**headers, "Idempotency-Key": "test-key-123"}

    res1 = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers_with_idempotency
    )
    assert res1.status_code == 201
    
    res2 = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers_with_idempotency
    )
    assert res2.status_code == 201
    assert res1.json()["id"] == res2.json()["id"]


async def test_booking_cancellation_and_state(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 201
    b_id = res.json()["id"]

    res_cancel = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings/{b_id}/cancel", headers=headers
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["booking_status"] == BookingStatus.CANCELLED
    
    # Try cancelling again
    res_cancel_again = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings/{b_id}/cancel", headers=headers
    )
    assert res_cancel_again.status_code == 422


async def test_unauthorized_booking_access(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 201
    b_id = res.json()["id"]

    # Try accessing with another user
    # We don't have a second user token fixture easily, but we can try without token
    res_unauth = await async_client.get(f"{settings.API_V1_PREFIX}/bookings/{b_id}")
    assert res_unauth.status_code == 401


async def test_payment_mock_failure(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json=booking_data,
        headers={**headers, "X-Payment-Token": "fail_token"},
    )
    assert res.status_code == 422
    assert "payment failed" in res.json()["error"]["message"].lower()

    # The availability should have been rolled back, so we can book again
    res2 = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res2.status_code == 201


@pytest.mark.skipif(
    settings.TEST_DATABASE_URL.startswith("sqlite"),
    reason="SQLite does not support the row-level locking needed for this test",
)
async def test_concurrent_booking_scenario(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Make concurrent requests
    tasks = [
        async_client.post(
            f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
        ) for _ in range(3)
    ]
    
    responses = await asyncio.gather(*tasks)
    
    successes = [r for r in responses if r.status_code == 201]
    failures = [r for r in responses if r.status_code == 422]
    
    # We should have exactly 1 success and 2 failures due to pessimistic locking in service
    assert len(successes) == 1
    assert len(failures) == 2
async def test_get_user_bookings(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Create a booking
    await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )

    # Get user bookings
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings", headers=headers
    )
    assert res.status_code == 200
    assert len(res.json()) >= 1


async def test_get_booking_by_id(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Create a booking
    create_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    b_id = create_res.json()["id"]

    # Get booking by id
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{b_id}", headers=headers
    )
    assert res.status_code == 200
    assert res.json()["id"] == b_id


async def test_successful_experience_booking(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "experience",
                "experience_id": str(exp_id),
                "start_date": start_d.isoformat(),
                "start_time": "10:00:00",
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 201
    assert res.json()["total"] == "60.00"  # price_override was 60


async def test_unavailable_experience(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "experience",
                "experience_id": str(exp_id),
                "start_date": start_d.isoformat(),
                "start_time": "10:00:00",
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Book once
    await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )

    # Book again
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 422
    assert "fully booked" in res.json()["error"]["message"].lower()


async def test_booking_multiple_items(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            },
            {
                "item_type": "experience",
                "experience_id": str(exp_id),
                "start_date": start_d.isoformat(),
                "start_time": "10:00:00",
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 201
    # total should be 2 days * 100 + 1 * 60 = 260.00
    assert res.json()["total"] == "260.00"
