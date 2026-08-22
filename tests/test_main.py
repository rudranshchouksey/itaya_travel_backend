import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    """Test GET /health returns 200 and the correct response."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_v1_router_registered():
    """Test that the /api/v1 prefix is correctly registered."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(f"{settings.API_V1_PREFIX}/docs")

    # FastAPIs /docs endpoint returns 200 by default.
    # If the router or prefix wasn't registered properly, this would fail (or if docs were disabled, but they are not).
    # Since we mounted the app with openapi_url and docs_url configured for API_V1_PREFIX, this should work.
    assert response.status_code == 200
