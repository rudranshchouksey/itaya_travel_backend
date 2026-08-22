import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.shared.models import Base, BaseModel

# Setup async test engine
test_engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


# Dummy model for testing persistence
class DummyModel(BaseModel):
    __tablename__ = "dummy_models"
    name: Mapped[str] = mapped_column(String, nullable=False)


@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    """Create and drop all tables before and after tests."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
