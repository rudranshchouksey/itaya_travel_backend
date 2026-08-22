import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_update_user_profile(async_client: AsyncClient):
    await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "update@example.com",
            "username": "updateuser",
            "password": "password123",
        },
    )
    login_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "update@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]

    update_res = await async_client.patch(
        f"{settings.API_V1_PREFIX}/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"first_name": "Updated First", "last_name": "Updated Last"},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["first_name"] == "Updated First"
    assert data["last_name"] == "Updated Last"
