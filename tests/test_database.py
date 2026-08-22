import pytest

from tests.conftest import DummyModel, TestSessionLocal


@pytest.mark.asyncio
async def test_database_health_endpoint(async_client):
    """Test the /health/database endpoint."""
    response = await async_client.get("/api/v1/health/database")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Database connection is healthy",
    }


@pytest.mark.asyncio
async def test_base_model_persistence():
    """Test that a model inheriting from BaseModel can be persisted with auto-fields."""
    async with TestSessionLocal() as session:
        dummy = DummyModel(name="test persistence")
        session.add(dummy)
        await session.commit()
        await session.refresh(dummy)

        assert dummy.id is not None
        assert dummy.created_at is not None
        assert dummy.updated_at is not None
        assert dummy.name == "test persistence"
