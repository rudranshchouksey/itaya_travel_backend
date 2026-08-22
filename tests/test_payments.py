import hashlib
import hmac
import json
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
        email=f"paymentuser_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"paymentuser_{uuid.uuid4().hex[:8]}",
        first_name="Payment",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"otheruser_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"otheruser_{uuid.uuid4().hex[:8]}",
        first_name="Other",
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


@pytest_asyncio.fixture
async def other_user_token(async_client: AsyncClient, other_user: User) -> str:
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": other_user.email, "password": "securepassword"},
    )
    return res.json()["access_token"]


async def create_test_booking(
    async_client: AsyncClient, token: str, db_session: AsyncSession, host_user: User
) -> dict:
    dest = Destination(
        name="Pay Dest",
        slug=f"pay-dest-{uuid.uuid4().hex[:8]}",
        country="IN",
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=host_user.id,
        destination_id=dest.id,
        title="Pay Listing",
        slug=f"pay-listing-{uuid.uuid4().hex[:8]}",
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
            price=Decimal("150.00"),
            is_available=True,
        )
        db_session.add(avail)
    await db_session.commit()

    res = await async_client.post(
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
            "guests": [{"first_name": "John", "last_name": "Doe", "is_primary": True}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()


async def test_payment_creation(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert "payment_id" in data
    assert "provider_order_id" in data
    assert data["amount"] == "300.00"
    assert data["currency"] == "INR"


async def test_payment_idempotency(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    idempotency_key = "idemp_pay_key_123"
    res1 = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"], "idempotency_key": idempotency_key},
        headers=headers,
    )
    assert res1.status_code == 201

    res2 = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"], "idempotency_key": idempotency_key},
        headers=headers,
    )
    assert res2.status_code == 201
    assert res1.json()["payment_id"] == res2.json()["payment_id"]


async def test_unauthorized_payment_creation(
    async_client: AsyncClient,
    test_user_token: str,
    other_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    # Other user tries to pay for test_user's booking
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert res.status_code == 403


async def test_get_payment_details(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    payment_id = p_res.json()["payment_id"]

    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["id"] == payment_id
    assert res.json()["status"] == PaymentStatus.CREATED


async def test_verify_payment_success(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    p_data = p_res.json()
    payment_id = p_data["payment_id"]

    v_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/verify",
        json={
            "payment_id": str(payment_id),
            "provider_payment_id": "pay_valid_123",
            "provider_order_id": p_data["provider_order_id"],
            "provider_signature": "sig_valid_123",
        },
        headers=headers,
    )
    assert v_res.status_code == 200
    assert v_res.json()["status"] == PaymentStatus.CAPTURED

    # Check booking confirmation
    b_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{booking['id']}",
        headers=headers,
    )
    assert b_res.json()["booking_status"] == BookingStatus.CONFIRMED


async def test_verify_payment_failure(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    p_data = p_res.json()
    payment_id = p_data["payment_id"]

    v_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/verify",
        json={
            "payment_id": str(payment_id),
            "provider_payment_id": "fail_token",
            "provider_order_id": p_data["provider_order_id"],
            "provider_signature": "sig_invalid",
        },
        headers=headers,
    )
    assert v_res.status_code == 422


async def test_webhook_processing_and_idempotency(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"]},
        headers=headers,
    )
    order_id = p_res.json()["provider_order_id"]

    webhook_payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_webhook_captured",
                    "order_id": order_id,
                    "amount": 30000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    body = json.dumps(webhook_payload).encode("utf-8")
    secret = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

    # 1. First webhook delivery
    w_res1 = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert w_res1.status_code == 200

    # Booking should be confirmed
    b_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{booking['id']}",
        headers=headers,
    )
    assert b_res.json()["booking_status"] == BookingStatus.CONFIRMED

    # 2. Duplicate webhook delivery
    w_res2 = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert w_res2.status_code == 200


async def test_webhook_invalid_signature(async_client: AsyncClient):
    webhook_payload = {
        "id": "evt_test_invalid_sig",
        "event": "payment.captured",
        "payload": {},
    }
    body = json.dumps(webhook_payload).encode("utf-8")

    w_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/webhooks/razorpay",
        content=body,
        headers={
            "X-Razorpay-Signature": "invalid_signature",
            "Content-Type": "application/json",
        },
    )
    assert w_res.status_code == 422
