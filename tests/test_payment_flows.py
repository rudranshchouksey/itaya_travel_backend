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
from app.modules.payments.service import FinancialService
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def traveler(db_session: AsyncSession) -> User:
    user = User(
        email=f"traveler_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"traveler_{uuid.uuid4().hex[:8]}",
        first_name="Traveler",
        last_name="Test",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def host(db_session: AsyncSession) -> User:
    user = User(
        email=f"hostflow_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"hostflow_{uuid.uuid4().hex[:8]}",
        first_name="HostFlow",
        last_name="Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def traveler_token(async_client: AsyncClient, traveler: User) -> str:
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": traveler.email, "password": "securepassword"},
    )
    return res.json()["access_token"]


async def create_inventory(
    db_session: AsyncSession, host: User
) -> tuple[uuid.UUID, date]:
    dest = Destination(
        name="Flow Dest",
        slug=f"flow-dest-{uuid.uuid4().hex[:8]}",
        country="TC",
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=host.id,
        destination_id=dest.id,
        title="Flow Listing",
        slug=f"flow-listing-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    start_d = date.today() + timedelta(days=7)
    for i in range(3):
        avail = ListingAvailability(
            listing_id=listing.id,
            date=start_d + timedelta(days=i),
            price=Decimal("100.00"),
            is_available=True,
        )
        db_session.add(avail)
    await db_session.commit()
    return listing.id, start_d


async def test_flow_a_successful_booking_to_settlement(
    async_client: AsyncClient,
    traveler_token: str,
    traveler: User,
    host: User,
    db_session: AsyncSession,
):
    """Flow A: Accommodation Booking -> Payment Intent -> Verification -> Confirmation -> Financials"""
    headers = {"Authorization": f"Bearer {traveler_token}"}
    listing_id, start_d = await create_inventory(db_session, host)

    # 1. Create booking
    b_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json={
            "currency": "USD",
            "items": [
                {
                    "item_type": "stay",
                    "listing_id": str(listing_id),
                    "start_date": start_d.isoformat(),
                    "end_date": (start_d + timedelta(days=2)).isoformat(),
                    "quantity": 1,
                    "guest_count": 2,
                }
            ],
            "guests": [
                {"first_name": "Traveler", "last_name": "T", "is_primary": True}
            ],
        },
        headers=headers,
    )
    assert b_res.status_code == 201
    booking_id = b_res.json()["id"]
    assert b_res.json()["booking_status"] == BookingStatus.PAYMENT_PENDING
    assert b_res.json()["total"] == "200.00"

    # 2. Create payment intent
    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking_id},
        headers=headers,
    )
    assert p_res.status_code == 201
    payment_id = p_res.json()["payment_id"]
    provider_order_id = p_res.json()["provider_order_id"]

    # 3. Verify payment signature
    v_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/verify",
        json={
            "payment_id": str(payment_id),
            "provider_payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "provider_order_id": provider_order_id,
            "provider_signature": "sig_mock",
        },
        headers=headers,
    )
    assert v_res.status_code == 200
    assert v_res.json()["status"] == PaymentStatus.CAPTURED

    # 4. Booking confirmed
    b_check = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}",
        headers=headers,
    )
    assert b_check.json()["booking_status"] == BookingStatus.CONFIRMED

    # 5. Financial check: 200 - (15% = 30) = 170.00 balance
    balance = await FinancialService.get_provider_balance(db_session, host.id)
    assert balance == Decimal("170.00")


async def test_flow_b_payment_failure_recovery(
    async_client: AsyncClient,
    traveler_token: str,
    traveler: User,
    host: User,
    db_session: AsyncSession,
):
    """Flow B: Payment verification fails -> booking remains payment_pending"""
    headers = {"Authorization": f"Bearer {traveler_token}"}
    listing_id, start_d = await create_inventory(db_session, host)

    b_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json={
            "currency": "USD",
            "items": [
                {
                    "item_type": "stay",
                    "listing_id": str(listing_id),
                    "start_date": start_d.isoformat(),
                    "end_date": (start_d + timedelta(days=2)).isoformat(),
                    "quantity": 1,
                    "guest_count": 2,
                }
            ],
            "guests": [
                {"first_name": "Traveler", "last_name": "T", "is_primary": True}
            ],
        },
        headers=headers,
    )
    booking_id = b_res.json()["id"]

    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking_id},
        headers=headers,
    )
    payment_id = p_res.json()["payment_id"]
    order_id = p_res.json()["provider_order_id"]

    v_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/{payment_id}/verify",
        json={
            "payment_id": str(payment_id),
            "provider_payment_id": "fail_token",
            "provider_order_id": order_id,
            "provider_signature": "sig_bad",
        },
        headers=headers,
    )
    assert v_res.status_code == 422

    # Booking should not be confirmed
    b_check = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}",
        headers=headers,
    )
    assert b_check.json()["booking_status"] == BookingStatus.PAYMENT_PENDING


async def test_flow_c_cancellation_and_ledger_reversal(
    async_client: AsyncClient,
    traveler_token: str,
    traveler: User,
    host: User,
    db_session: AsyncSession,
):
    """Flow C: Confirmed booking cancelled > 48h in advance -> refund & financial ledger reversal"""
    headers = {"Authorization": f"Bearer {traveler_token}"}
    listing_id, start_d = await create_inventory(db_session, host)

    # 1. Book & Pay
    b_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings",
        json={
            "currency": "USD",
            "items": [
                {
                    "item_type": "stay",
                    "listing_id": str(listing_id),
                    "start_date": start_d.isoformat(),
                    "end_date": (start_d + timedelta(days=2)).isoformat(),
                    "quantity": 1,
                    "guest_count": 2,
                }
            ],
            "guests": [
                {"first_name": "Traveler", "last_name": "T", "is_primary": True}
            ],
        },
        headers=headers,
    )
    booking_id = b_res.json()["id"]

    p_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking_id},
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

    # Balance before cancel: +170
    balance_before = await FinancialService.get_provider_balance(db_session, host.id)
    assert balance_before == Decimal("170.00")

    # 2. Cancel booking (7 days in advance -> 100% refund)
    c_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings/{booking_id}/cancel",
        json={"reason": "Plans changed"},
        headers=headers,
    )
    assert c_res.status_code == 200
    assert c_res.json()["booking_status"] == BookingStatus.CANCELLED

    # Balance after cancel: 170 - 200 = -30 (or reversed)
    balance_after = await FinancialService.get_provider_balance(db_session, host.id)
    assert balance_after == Decimal("-30.00")
