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
from app.modules.payments.service import FinancialService
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def host_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"host_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"host_{uuid.uuid4().hex[:8]}",
        first_name="Host",
        last_name="Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def guest_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"guest_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"guest_{uuid.uuid4().hex[:8]}",
        first_name="Guest",
        last_name="Traveler",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def guest_user_token(async_client: AsyncClient, guest_user: User) -> str:
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": guest_user.email, "password": "securepassword"},
    )
    return res.json()["access_token"]


async def test_platform_commission_and_provider_payable(
    async_client: AsyncClient,
    guest_user_token: str,
    db_session: AsyncSession,
    host_user: User,
):
    headers = {"Authorization": f"Bearer {guest_user_token}"}
    dest = Destination(
        name="Fin Dest",
        slug=f"fin-dest-{uuid.uuid4().hex[:8]}",
        country="IN",
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=host_user.id,
        destination_id=dest.id,
        title="Fin Listing",
        slug=f"fin-listing-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    start_d = date.today() + timedelta(days=10)
    avail = ListingAvailability(
        listing_id=listing.id,
        date=start_d,
        price=Decimal("1000.00"),
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
                    "end_date": (start_d + timedelta(days=1)).isoformat(),
                    "quantity": 1,
                    "guest_count": 2,
                }
            ],
            "guests": [{"first_name": "G", "last_name": "T", "is_primary": True}],
        },
        headers=headers,
    )
    assert res.status_code == 201
    b_data = res.json()

    # 15% platform fee on 1000 = 150.00
    assert b_data["subtotal"] == "1000.00"
    assert b_data["platform_fee"] == "150.00"
    assert b_data["provider_amount"] == "850.00"
    assert b_data["total"] == "1000.00"


async def test_financial_ledger_entries_and_provider_balance(
    async_client: AsyncClient,
    guest_user_token: str,
    db_session: AsyncSession,
    host_user: User,
):
    headers = {"Authorization": f"Bearer {guest_user_token}"}
    dest = Destination(
        name="Fin Dest 2",
        slug=f"fin-dest2-{uuid.uuid4().hex[:8]}",
        country="IN",
    )
    db_session.add(dest)
    await db_session.flush()

    listing = Listing(
        host_id=host_user.id,
        destination_id=dest.id,
        title="Fin Listing 2",
        slug=f"fin-listing2-{uuid.uuid4().hex[:8]}",
        property_type=PropertyType.HOTEL,
        guest_capacity=2,
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    await db_session.flush()

    start_d = date.today() + timedelta(days=10)
    avail = ListingAvailability(
        listing_id=listing.id,
        date=start_d,
        price=Decimal("500.00"),
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
                    "end_date": (start_d + timedelta(days=1)).isoformat(),
                    "quantity": 1,
                    "guest_count": 2,
                }
            ],
            "guests": [{"first_name": "G", "last_name": "T", "is_primary": True}],
        },
        headers=headers,
    )
    booking = b_res.json()

    # 2. Pay and confirm
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

    # 3. Check provider balance via FinancialService
    balance = await FinancialService.get_provider_balance(db_session, host_user.id)
    # Total credit: +500, Platform fee: -75 -> Net balance: +425.00
    assert balance == Decimal("425.00")
