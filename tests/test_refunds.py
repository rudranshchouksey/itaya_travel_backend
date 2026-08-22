import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.destinations.models import Destination
from app.modules.listings.models import (
    Listing,
    ListingAvailability,
    ListingStatus,
    PropertyType,
)
from app.modules.payments.models import PaymentStatus, RefundStatus
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"refunduser_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"refunduser_{uuid.uuid4().hex[:8]}",
        first_name="Refund",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"otherrefund_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"otherrefund_{uuid.uuid4().hex[:8]}",
        first_name="Other",
        last_name="Refund",
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


@pytest_asyncio.fixture
async def other_user_token(async_client: AsyncClient, other_user: User) -> str:
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": other_user.email, "password": "securepassword"},
    )
    return res.json()["access_token"]


async def setup_captured_payment(
    async_client: AsyncClient, token: str, db_session: AsyncSession, host_user: User
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    dest = Destination(
        name="Refund Dest",
        slug=f"refund-dest-{uuid.uuid4().hex[:8]}",
        country="IN",
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=host_user.id,
        destination_id=dest.id,
        title="Refund Listing",
        slug=f"refund-listing-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    start_d = date.today() + timedelta(days=5)
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
            "currency": "INR",
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
            "guests": [{"first_name": "Jane", "last_name": "Doe", "is_primary": True}],
        },
        headers=headers,
    )
    booking = b_res.json()

    # 2. Create payment
    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    p_data = p_res.json()
    payment_id = p_data["payment_id"]

    # 3. Verify payment
    await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/verify",
        json={
            "payment_id": str(payment_id),
            "provider_payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "provider_order_id": p_data["provider_order_id"],
            "provider_signature": "sig_valid",
        },
        headers=headers,
    )

    return {"booking_id": booking["id"], "payment_id": payment_id}


async def test_full_refund(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    setup = await setup_captured_payment(
        async_client, test_user_token, db_session, test_user
    )
    payment_id = setup["payment_id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/refund",
        json={
            "payment_id": payment_id,
            "amount": "200.00",
            "reason": "Customer request",
        },
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["amount"] == "200.00"
    assert data["status"] == RefundStatus.COMPLETED

    # Payment status should now be refunded
    p_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}",
        headers=headers,
    )
    assert p_res.json()["status"] == PaymentStatus.REFUNDED


async def test_partial_refund(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    setup = await setup_captured_payment(
        async_client, test_user_token, db_session, test_user
    )
    payment_id = setup["payment_id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/refund",
        json={
            "payment_id": payment_id,
            "amount": "50.00",
            "reason": "Partial compensation",
        },
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json()["amount"] == "50.00"

    p_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}",
        headers=headers,
    )
    assert p_res.json()["status"] == PaymentStatus.PARTIALLY_REFUNDED


async def test_refund_exceeding_amount(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    setup = await setup_captured_payment(
        async_client, test_user_token, db_session, test_user
    )
    payment_id = setup["payment_id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/refund",
        json={"payment_id": payment_id, "amount": "500.00"},
        headers=headers,
    )
    assert res.status_code == 422


async def test_refund_idempotency(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    setup = await setup_captured_payment(
        async_client, test_user_token, db_session, test_user
    )
    payment_id = setup["payment_id"]

    idempotency_key = "rfnd_idemp_key_123"
    res1 = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/refund",
        json={
            "payment_id": payment_id,
            "amount": "50.00",
            "idempotency_key": idempotency_key,
        },
        headers=headers,
    )
    assert res1.status_code == 201

    res2 = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/refund",
        json={
            "payment_id": payment_id,
            "amount": "50.00",
            "idempotency_key": idempotency_key,
        },
        headers=headers,
    )
    assert res2.status_code == 201
    assert res1.json()["id"] == res2.json()["id"]


async def test_unauthorized_refund(
    async_client: AsyncClient,
    test_user_token: str,
    other_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    setup = await setup_captured_payment(
        async_client, test_user_token, db_session, test_user
    )
    payment_id = setup["payment_id"]

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/refund",
        json={"payment_id": payment_id, "amount": "50.00"},
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert res.status_code == 403
