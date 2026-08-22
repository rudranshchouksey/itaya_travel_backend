from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.destinations.models import Destination
from app.modules.destinations.schemas import DestinationCreate


class DestinationService:
    @staticmethod
    async def create_destination(
        session: AsyncSession, destination_in: DestinationCreate
    ) -> Destination:
        destination = Destination(**destination_in.model_dump())
        session.add(destination)
        await session.commit()
        await session.refresh(destination)
        return destination

    @staticmethod
    async def get_by_slug(
        session: AsyncSession, slug: str, only_active: bool = True
    ) -> Destination | None:
        stmt = select(Destination).where(Destination.slug == slug)
        if only_active:
            stmt = stmt.where(Destination.is_active == True)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_destinations(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
        country: str | None = None,
        only_active: bool = True,
    ) -> Sequence[Destination]:
        stmt = select(Destination).offset(skip).limit(limit)

        # Default sort by name
        stmt = stmt.order_by(Destination.name)

        if only_active:
            stmt = stmt.where(Destination.is_active == True)

        if search:
            stmt = stmt.where(Destination.name.ilike(f"%{search}%"))

        if country:
            stmt = stmt.where(Destination.country == country)

        result = await session.execute(stmt)
        return result.scalars().all()
