import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.experiences.models import (
    Experience,
    ExperienceAvailability,
    ExperienceCategoryLink,
    ExperienceStatus,
)
from app.modules.experiences.schemas import ExperienceCreate, ExperienceUpdate


class ExperienceService:
    @staticmethod
    async def create_experience(
        session: AsyncSession, *, provider_id: uuid.UUID, obj_in: ExperienceCreate
    ) -> Experience:
        db_obj = Experience(
            provider_id=provider_id,
            destination_id=obj_in.destination_id,
            title=obj_in.title,
            slug=obj_in.slug,
            description=obj_in.description,
            duration_minutes=obj_in.duration_minutes,
            guest_capacity=obj_in.guest_capacity,
            base_price=obj_in.base_price,
            currency=obj_in.currency,
            meeting_point=obj_in.meeting_point,
            status=obj_in.status,
        )
        session.add(db_obj)
        await session.flush()

        if obj_in.category_ids:
            for cat_id in set(obj_in.category_ids):
                link = ExperienceCategoryLink(
                    experience_id=db_obj.id, category_id=cat_id
                )
                session.add(link)

        await session.commit()
        return await ExperienceService.get_by_id(session, id=db_obj.id)

    @staticmethod
    async def get_by_slug(
        session: AsyncSession, *, slug: str, public_only: bool = True
    ) -> Experience | None:
        stmt = (
            select(Experience)
            .options(
                selectinload(Experience.categories), selectinload(Experience.images)
            )
            .where(Experience.slug == slug)
        )

        if public_only:
            stmt = stmt.where(Experience.status == ExperienceStatus.PUBLISHED)

        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_id(session: AsyncSession, *, id: uuid.UUID) -> Experience | None:
        stmt = (
            select(Experience)
            .options(
                selectinload(Experience.categories), selectinload(Experience.images)
            )
            .where(Experience.id == id)
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_experiences(
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
        destination_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        max_price: Decimal | None = None,
        public_only: bool = True,
    ) -> Sequence[Experience]:
        stmt = select(Experience).options(
            selectinload(Experience.categories), selectinload(Experience.images)
        )

        if destination_id:
            stmt = stmt.where(Experience.destination_id == destination_id)

        if category_id:
            stmt = stmt.join(ExperienceCategoryLink).where(
                ExperienceCategoryLink.category_id == category_id
            )

        if max_price is not None:
            stmt = stmt.where(Experience.base_price <= max_price)

        if public_only:
            stmt = stmt.where(Experience.status == ExperienceStatus.PUBLISHED)

        stmt = stmt.offset(skip).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_experience(
        session: AsyncSession,
        *,
        db_obj: Experience,
        obj_in: ExperienceUpdate,
    ) -> Experience:
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"category_ids"})

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        if obj_in.category_ids is not None:
            # Clear old categories
            await session.execute(
                delete(ExperienceCategoryLink).where(
                    ExperienceCategoryLink.experience_id == db_obj.id
                )
            )
            # Add new
            for cat_id in set(obj_in.category_ids):
                link = ExperienceCategoryLink(
                    experience_id=db_obj.id, category_id=cat_id
                )
                session.add(link)

        session.add(db_obj)
        await session.commit()
        return await ExperienceService.get_by_id(session, id=db_obj.id)

    @staticmethod
    async def get_availability(
        session: AsyncSession,
        *,
        experience_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Sequence[ExperienceAvailability]:
        stmt = (
            select(ExperienceAvailability)
            .where(
                ExperienceAvailability.experience_id == experience_id,
                ExperienceAvailability.date >= start_date,
                ExperienceAvailability.date <= end_date,
                ExperienceAvailability.is_available.is_(True),
            )
            .order_by(ExperienceAvailability.date, ExperienceAvailability.start_time)
        )
        result = await session.execute(stmt)
        return result.scalars().all()
