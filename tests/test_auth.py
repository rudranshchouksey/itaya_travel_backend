import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "test2@example.com",
            "username": "testuser2",
            "password": "password123",
        },
    )
    response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "test2@example.com",
            "username": "different_user",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "email already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(async_client: AsyncClient):
    await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "test3@example.com",
            "username": "testuser3",
            "password": "password123",
        },
    )
    response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "different@example.com",
            "username": "testuser3",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "username already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_password(async_client: AsyncClient):
    response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "test4@example.com",
            "username": "testuser4",
            "password": "short",
        },
    )
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "password123",
        },
    )
    response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient):
    response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "wrong@example.com", "password": "password123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_and_password_not_returned(async_client: AsyncClient):
    await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "me@example.com",
            "username": "meuser",
            "password": "password123",
        },
    )
    login_response = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "me@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = await async_client.get(
        f"{settings.API_V1_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_auth_me_unauthorized(async_client: AsyncClient):
    response = await async_client.get(f"{settings.API_V1_PREFIX}/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_and_logout(async_client: AsyncClient):
    await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={
            "email": "refresh@example.com",
            "username": "refreshuser",
            "password": "password123",
        },
    )
    login_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "refresh@example.com", "password": "password123"},
    )
    tokens = login_res.json()
    refresh = tokens["refresh_token"]

    refresh_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/refresh", json={"refresh_token": refresh}
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()

    logout_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/logout",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout_res.status_code == 200

    me_res = await async_client.get(
        f"{settings.API_V1_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me_res.status_code == 401
