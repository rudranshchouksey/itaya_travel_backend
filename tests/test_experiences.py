from datetime import date, time, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.modules.destinations.models import Destination
from app.modules.experiences.models import (
    Experience,
    ExperienceAvailability,
    ExperienceCategory,
    ExperienceCategoryLink,
    ExperienceStatus,
)
from app.modules.users.models import Role, User, UserRole


@pytest_asyncio.fixture
async def experience_provider(db_session: AsyncSession) -> User:
    user = User(
        email="provider@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username="expprovider",
        first_name="Exp",
        last_name="Provider",
    )
    db_session.add(user)
    await db_session.commit()

    # Add role
    role = UserRole(user_id=user.id, role=Role.EXPERIENCE_PROVIDER)
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        email="traveler@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username="traveler",
        first_name="Regular",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def exp_destination(db_session: AsyncSession) -> Destination:
    dest = Destination(name="Kyoto", slug="kyoto-jp", country="Japan")
    db_session.add(dest)
    await db_session.commit()
    await db_session.refresh(dest)
    return dest


@pytest_asyncio.fixture
async def exp_category(db_session: AsyncSession) -> ExperienceCategory:
    cat = ExperienceCategory(name="Cultural", slug="cultural")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest_asyncio.fixture
async def sample_experience(
    db_session: AsyncSession,
    experience_provider: User,
    exp_destination: Destination,
    exp_category: ExperienceCategory,
) -> Experience:
    exp = Experience(
        provider_id=experience_provider.id,
        destination_id=exp_destination.id,
        title="Tea Ceremony",
        slug="tea-ceremony-kyoto",
        description="Authentic tea ceremony",
        duration_minutes=90,
        guest_capacity=6,
        base_price=Decimal("50.00"),
        status=ExperienceStatus.PUBLISHED,
    )
    db_session.add(exp)
    await db_session.flush()

    link = ExperienceCategoryLink(experience_id=exp.id, category_id=exp_category.id)
    db_session.add(link)

    avail = ExperienceAvailability(
        experience_id=exp.id,
        date=date.today() + timedelta(days=2),
        start_time=time(10, 0),
        end_time=time(11, 30),
        price_override=Decimal("60.00"),
        is_available=True,
    )
    db_session.add(avail)

    await db_session.commit()
    await db_session.refresh(exp)
    return exp


@pytest.mark.asyncio
async def test_experience_creation(
    async_client: AsyncClient,
    experience_provider: User,
    exp_destination: Destination,
    exp_category: ExperienceCategory,
):
    # Log in as provider
    login_data = {"username": experience_provider.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # 1. Experience creation
    exp_in = {
        "destination_id": str(exp_destination.id),
        "title": "Cooking Class",
        "slug": "cooking-class-kyoto",
        "description": "Learn to cook",
        "duration_minutes": 120,
        "guest_capacity": 4,
        "base_price": "75.00",
        "category_ids": [str(exp_category.id)],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences",
        json=exp_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Cooking Class"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_unauthorized_creation(
    async_client: AsyncClient,
    regular_user: User,
    exp_destination: Destination,
):
    # Log in as regular user
    login_data = {"username": regular_user.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    exp_in = {
        "destination_id": str(exp_destination.id),
        "title": "Unauthorized",
        "slug": "unauthorized-exp",
        "duration_minutes": 60,
        "guest_capacity": 2,
        "base_price": "10.00",
    }

    # 7. Provider ownership / capability
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences",
        json=exp_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_experience_retrieval(
    async_client: AsyncClient,
    sample_experience: Experience,
):
    # 2. Experience retrieval
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/experiences/{sample_experience.slug}"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Tea Ceremony"
    assert len(data["categories"]) == 1
    assert data["categories"][0]["name"] == "Cultural"


@pytest.mark.asyncio
async def test_experience_filtering(
    async_client: AsyncClient,
    sample_experience: Experience,
    exp_destination: Destination,
    exp_category: ExperienceCategory,
):
    # 3. Destination filtering
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/experiences?destination_id={exp_destination.id}"
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 4. Category filtering
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/experiences?category_id={exp_category.id}"
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 5. Price filtering
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/experiences?max_price=40.00"
    )
    assert res.status_code == 200
    assert len(res.json()) == 0

    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/experiences?max_price=60.00"
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_availability(
    async_client: AsyncClient,
    sample_experience: Experience,
    experience_provider: User,
):
    start_date = date.today().isoformat()
    end_date = (date.today() + timedelta(days=5)).isoformat()

    # 6. Availability lookup
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/experiences/{sample_experience.id}/availability?start_date={start_date}&end_date={end_date}"
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["price_override"] == "60.00"

    # Add availability block
    login_data = {"username": experience_provider.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    block = {
        "date": (date.today() + timedelta(days=3)).isoformat(),
        "start_time": "14:00:00",
        "end_time": "16:00:00",
        "price_override": "55.00",
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences/{sample_experience.id}/availability",
        json=[block],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # 12. Invalid duration
    invalid_block = block.copy()
    invalid_block["end_time"] = "13:00:00"  # before start_time
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences/{sample_experience.id}/availability",
        json=[invalid_block],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_unauthorized_modification(
    async_client: AsyncClient,
    sample_experience: Experience,
    db_session: AsyncSession,
):
    # Create another provider
    user2 = User(
        email="provider2@itvaya.com",
        password_hash=get_password_hash("securepassword"),
        username="expprovider2",
    )
    db_session.add(user2)
    await db_session.commit()

    role = UserRole(user_id=user2.id, role=Role.EXPERIENCE_PROVIDER)
    db_session.add(role)
    await db_session.commit()

    login_data = {"username": user2.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    # 8. Unauthorized modification
    res = await async_client.put(
        f"{settings.API_V1_PREFIX}/experiences/{sample_experience.id}",
        json={"title": "Hacked"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_publishing(
    async_client: AsyncClient,
    experience_provider: User,
    exp_destination: Destination,
    db_session: AsyncSession,
):
    # Log in as provider
    login_data = {"username": experience_provider.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    exp = Experience(
        provider_id=experience_provider.id,
        destination_id=exp_destination.id,
        title="Draft Exp",
        slug="draft-exp",
        duration_minutes=30,
        guest_capacity=2,
        base_price=Decimal("10.00"),
        status=ExperienceStatus.DRAFT,
    )
    db_session.add(exp)
    await db_session.commit()

    # 13. Public access (draft should not be visible)
    res = await async_client.get(f"{settings.API_V1_PREFIX}/experiences/draft-exp")
    assert res.status_code == 404

    # 9. Publishing
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences/{exp.id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "published"

    # Now it should be visible
    res = await async_client.get(f"{settings.API_V1_PREFIX}/experiences/draft-exp")
    assert res.status_code == 200

    # 10. Unpublishing
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences/{exp.id}/unpublish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "unlisted"


@pytest.mark.asyncio
async def test_capacity_validation(
    async_client: AsyncClient,
    experience_provider: User,
    exp_destination: Destination,
):
    login_data = {"username": experience_provider.email, "password": "securepassword"}
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/auth/login", data=login_data
    )
    token = res.json()["access_token"]

    exp_in = {
        "destination_id": str(exp_destination.id),
        "title": "Invalid Capacity",
        "slug": "invalid-cap",
        "duration_minutes": 60,
        "guest_capacity": 0,  # 11. Capacity validation (must be > 0)
        "base_price": "10.00",
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/experiences",
        json=exp_in,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_database_constraints(
    db_session: AsyncSession,
    sample_experience: Experience,
):
    # 14. Database constraints (duplicate slug)
    from sqlalchemy.exc import IntegrityError

    exp2 = Experience(
        provider_id=sample_experience.provider_id,
        destination_id=sample_experience.destination_id,
        title="Duplicate",
        slug=sample_experience.slug,
        duration_minutes=30,
        guest_capacity=1,
        base_price=Decimal("10.00"),
    )
    db_session.add(exp2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
