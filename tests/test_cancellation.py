import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.bookings.models import BookingStatus
from app.modules.destinations.models import Destination
from app.modules.listings.models import (
    Listing,
    ListingAvailability,
    ListingStatus,
    PropertyType,
)
from app.modules.payments.models import PaymentStatus
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"canceluser_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"canceluser_{uuid.uuid4().hex[:8]}",
        first_name="Cancel",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_token(async_client: AsyncClient, test_user: User) -> str:
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": test_user.email, "password": "securepassword"},
    )
    return res.json()["access_token"]


async def create_confirmed_booking(
    async_client: AsyncClient,
    token: str,
    db_session: AsyncSession,
    host_user: User,
    days_in_advance: int = 5,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    dest = Destination(
        name="Cancel Dest",
        slug=f"cancel-dest-{uuid.uuid4().hex[:8]}",
        country="TC",
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=host_user.id,
        destination_id=dest.id,
        title="Cancel Listing",
        slug=f"cancel-listing-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    start_d = date.today() + timedelta(days=days_in_advance)
    for i in range(2):
        avail = ListingAvailability(
            listing_id=listing.id,
            date=start_d + timedelta(days=i),
            price=Decimal("100.00"),
            is_available=True,
        )
        db_session.add(avail)
    await db_session.commit()

    # 1. Create booking
    b_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json={
            "currency": "USD",
            "items": [
                {
                    "item_type": "stay",
                    "listing_id": str(listing.id),
                    "start_date": start_d.isoformat(),
                    "end_date": (start_d + timedelta(days=2)).isoformat(),
                    "quantity": 1,
                    "guest_count": 2,
                }
            ],
            "guests": [
                {"first_name": "Test", "last_name": "Cancel", "is_primary": True}
            ],
        },
        headers=headers,
    )
    booking = b_res.json()

    # 2. Create and verify payment
    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    payment_id = p_res.json()["payment_id"]

    await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/verify",
        json={
            "payment_id": str(payment_id),
            "provider_payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "provider_order_id": p_res.json()["provider_order_id"],
            "provider_signature": "sig_valid",
        },
        headers=headers,
    )

    return {"booking_id": booking["id"], "payment_id": payment_id}


async def test_cancellation_full_refund(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    # 5 days in advance -> > 48h -> 100% refund
    headers = {"Authorization": f"Bearer {test_user_token}"}
    setup = await create_confirmed_booking(
        async_client, test_user_token, db_session, test_user, days_in_advance=5
    )
    booking_id = setup["booking_id"]
    payment_id = setup["payment_id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}/cancel",
        json={"reason": "Trip postponed"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["booking_status"] == BookingStatus.CANCELLED

    # Payment should be REFUNDED
    p_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}",
        headers=headers,
    )
    assert p_res.json()["status"] == PaymentStatus.REFUNDED


async def test_cancellation_partial_refund(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    # 1 day in advance -> 24h-48h -> 50% refund
    headers = {"Authorization": f"Bearer {test_user_token}"}
    setup = await create_confirmed_booking(
        async_client, test_user_token, db_session, test_user, days_in_advance=1
    )
    booking_id = setup["booking_id"]
    payment_id = setup["payment_id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}/cancel",
        json={"reason": "Emergency"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["booking_status"] == BookingStatus.CANCELLED

    # Payment should be PARTIALLY_REFUNDED
    p_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}",
        headers=headers,
    )
    assert p_res.json()["status"] == PaymentStatus.PARTIALLY_REFUNDED


async def test_cancellation_unconfirmed_booking(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    dest = Destination(
        name="Dest Unconf", slug=f"dest-unconf-{uuid.uuid4().hex[:8]}", country="TC"
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=test_user.id,
        destination_id=dest.id,
        title="Unconf Listing",
        slug=f"unconf-listing-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    start_d = date.today() + timedelta(days=3)
    avail = ListingAvailability(
        listing_id=listing.id,
        date=start_d,
        price=Decimal("100.00"),
        is_available=True,
    )
    db_session.add(avail)
    await db_session.commit()

    b_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json={
            "currency": "USD",
            "items": [
                {
                    "item_type": "stay",
                    "listing_id": str(listing.id),
                    "start_date": start_d.isoformat(),
                    "end_date": (start_d + timedelta(days=1)).isoformat(),
                    "quantity": 1,
                    "guest_count": 1,
                }
            ],
            "guests": [{"first_name": "Test", "last_name": "User", "is_primary": True}],
        },
        headers=headers,
    )
    booking_id = b_res.json()["id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}/cancel",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["booking_status"] == BookingStatus.CANCELLED
