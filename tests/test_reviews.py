import uuid
from datetime import date, timedelta, time
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
    PaymentStatus,
)
from app.modules.destinations.models import Destination
from app.modules.experiences.models import Experience, ExperienceStatus
from app.modules.listings.models import Listing, ListingStatus, PropertyType
from app.modules.trips.models import TripItemType
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"reviewuser_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"reviewuser_{uuid.uuid4().hex[:8]}",
        first_name="Review",
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


async def setup_review_data(db_session: AsyncSession, test_user: User):
    dest = Destination(name="Review Dest", slug=f"rev-dest-{uuid.uuid4().hex[:8]}", country="TC")
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=test_user.id,
        destination_id=dest.id,
        title="Review Listing",
        slug=f"rev-list-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    
    exp = Experience(
        provider_id=test_user.id,
        destination_id=dest.id,
        title="Review Exp",
        slug=f"rev-exp-{uuid.uuid4().hex[:8]}",
        duration_minutes=120,
        guest_capacity=10,
        base_price=Decimal("50.00"),
        status=ExperienceStatus.PUBLISHED,
    )
    db_session.add(exp)
    await db_session.flush()

    # Create completed booking
    booking = Booking(
        user_id=test_user.id,
        reference=f"BKG-REV-{uuid.uuid4().hex[:4]}",
        currency="USD",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        booking_status=BookingStatus.COMPLETED,
        payment_status=PaymentStatus.PAID,
    )
    db_session.add(booking)
    await db_session.flush()

    b_item_stay = BookingItem(
        booking_id=booking.id,
        item_type=TripItemType.STAY,
        listing_id=listing.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        price_snapshot=Decimal("100.00"),
        subtotal=Decimal("100.00"),
    )
    db_session.add(b_item_stay)

    b_item_exp = BookingItem(
        booking_id=booking.id,
        item_type=TripItemType.EXPERIENCE,
        experience_id=exp.id,
        start_date=date.today(),
        start_time=time(10, 0, 0),
        price_snapshot=Decimal("50.00"),
        subtotal=Decimal("50.00"),
    )
    db_session.add(b_item_exp)

    # Pending booking for validation test
    pending_booking = Booking(
        user_id=test_user.id,
        reference=f"BKG-PEND-{uuid.uuid4().hex[:4]}",
        currency="USD",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        booking_status=BookingStatus.PENDING,
        payment_status=PaymentStatus.PENDING,
    )
    db_session.add(pending_booking)
    await db_session.flush()

    b_item_pending = BookingItem(
        booking_id=pending_booking.id,
        item_type=TripItemType.STAY,
        listing_id=listing.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        price_snapshot=Decimal("100.00"),
        subtotal=Decimal("100.00"),
    )
    db_session.add(b_item_pending)

    await db_session.commit()
    return listing.id, exp.id, b_item_stay.id, b_item_exp.id, b_item_pending.id


async def test_valid_review(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    listing_id, exp_id, stay_item_id, exp_item_id, pending_item_id = await setup_review_data(db_session, test_user)
    headers = {"Authorization": f"Bearer {test_user_token}"}

    review_data = {
        "booking_item_id": str(stay_item_id),
        "rating": 5,
        "title": "Great Stay",
        "body": "It was amazing!"
    }
    res = await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers)
    assert res.status_code == 201
    assert res.json()["rating"] == 5


async def test_review_without_completed_booking(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    listing_id, exp_id, stay_item_id, exp_item_id, pending_item_id = await setup_review_data(db_session, test_user)
    headers = {"Authorization": f"Bearer {test_user_token}"}

    review_data = {
        "booking_item_id": str(pending_item_id),
        "rating": 5,
    }
    res = await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers)
    assert res.status_code == 422
    assert "completed" in res.json()["error"]["message"].lower()


async def test_duplicate_review(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    listing_id, exp_id, stay_item_id, exp_item_id, pending_item_id = await setup_review_data(db_session, test_user)
    headers = {"Authorization": f"Bearer {test_user_token}"}

    review_data = {
        "booking_item_id": str(stay_item_id),
        "rating": 5,
    }
    await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers)
    
    # second time
    res = await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers)
    assert res.status_code == 422
    assert "already reviewed" in res.json()["error"]["message"].lower()


async def test_invalid_rating(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    listing_id, exp_id, stay_item_id, exp_item_id, pending_item_id = await setup_review_data(db_session, test_user)
    headers = {"Authorization": f"Bearer {test_user_token}"}

    review_data = {
        "booking_item_id": str(stay_item_id),
        "rating": 6,
    }
    res = await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers)
    assert res.status_code == 422


async def test_unauthorized_review(async_client: AsyncClient, db_session: AsyncSession, test_user: User):
    # Setup as test_user, but we will make request with NO auth or different user auth
    listing_id, exp_id, stay_item_id, exp_item_id, pending_item_id = await setup_review_data(db_session, test_user)

    review_data = {
        "booking_item_id": str(stay_item_id),
        "rating": 4,
    }
    res = await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data)
    assert res.status_code == 401


async def test_review_retrieval(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    listing_id, exp_id, stay_item_id, exp_item_id, pending_item_id = await setup_review_data(db_session, test_user)
    headers = {"Authorization": f"Bearer {test_user_token}"}

    review_data = {
        "booking_item_id": str(stay_item_id),
        "rating": 5,
        "title": "Nice!"
    }
    await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data, headers=headers)

    review_data_exp = {
        "booking_item_id": str(exp_item_id),
        "rating": 4,
        "title": "Great Experience"
    }
    await async_client.post(f"{settings.API_V1_PREFIX}/reviews", json=review_data_exp, headers=headers)

    # Get listing reviews
    res_list = await async_client.get(f"{settings.API_V1_PREFIX}/listings/{listing_id}/reviews")
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1
    assert res_list.json()[0]["title"] == "Nice!"

    # Get experience reviews
    res_exp = await async_client.get(f"{settings.API_V1_PREFIX}/experiences/{exp_id}/reviews")
    assert res_exp.status_code == 200
    assert len(res_exp.json()) == 1
    assert res_exp.json()[0]["title"] == "Great Experience"
