import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.payments.models import PaymentStatus
from app.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    from app.core.security import get_password_hash
    user = User(
        email=f"stripe_user_{uuid.uuid4().hex[:8]}@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username=f"stripe_user_{uuid.uuid4().hex[:8]}",
        first_name="Stripe",
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


async def test_currency_resolution_usd_via_headers(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    from tests.test_payments import create_test_booking
    
    headers = {
        "Authorization": f"Bearer {test_user_token}",
        "CF-IPCountry": "US",
    }
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
    assert data["currency"] == "USD"


async def test_currency_resolution_explicit_payload(
    async_client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_user: User,
):
    from tests.test_payments import create_test_booking
    
    headers = {
        "Authorization": f"Bearer {test_user_token}",
    }
    booking = await create_test_booking(
        async_client, test_user_token, db_session, test_user
    )

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/payments/create",
        json={"booking_id": booking["id"], "user_currency": "GBP"},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["currency"] == "GBP"
