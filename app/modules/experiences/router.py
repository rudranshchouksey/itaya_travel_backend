import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, get_current_active_user
from app.modules.experiences.models import ExperienceAvailability, ExperienceStatus
from app.modules.experiences.schemas import (
    AvailabilityBlockCreate,
    ExperienceAvailabilityRead,
    ExperienceCreate,
    ExperienceRead,
    ExperienceSummary,
    ExperienceUpdate,
)
from app.modules.experiences.service import ExperienceService
from app.modules.users.models import Role, User

router = APIRouter()


def require_provider(user: User = Depends(get_current_active_user)) -> User:
    if not any(r.role == Role.EXPERIENCE_PROVIDER for r in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have EXPERIENCE_PROVIDER capability",
        )
    return user


@router.get("", response_model=list[ExperienceSummary])
async def search_experiences(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    destination_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    max_price: Decimal | None = None,
) -> Sequence[ExperienceSummary]:
    return await ExperienceService.get_experiences(
        session=session,
        skip=skip,
        limit=limit,
        destination_id=destination_id,
        category_id=category_id,
        max_price=max_price,
        public_only=True,
    )


@router.get("/{slug}", response_model=ExperienceRead)
async def get_experience_by_slug(slug: str, session: SessionDep) -> ExperienceRead:
    exp = await ExperienceService.get_by_slug(session, slug=slug, public_only=True)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    return exp


@router.get("/{id}/availability", response_model=list[ExperienceAvailabilityRead])
async def get_experience_availability(
    id: uuid.UUID,
    start_date: date,
    end_date: date,
    session: SessionDep,
) -> Sequence[ExperienceAvailabilityRead]:
    if end_date < start_date:
        raise HTTPException(
            status_code=400, detail="end_date cannot be before start_date"
        )
    if start_date < date.today():  # noqa: DTZ011
        raise HTTPException(status_code=400, detail="start_date cannot be in the past")

    return await ExperienceService.get_availability(
        session=session, experience_id=id, start_date=start_date, end_date=end_date
    )


@router.post("", response_model=ExperienceRead, status_code=status.HTTP_201_CREATED)
async def create_experience(
    exp_in: ExperienceCreate,
    session: SessionDep,
    current_user: User = Depends(require_provider),
) -> ExperienceRead:
    return await ExperienceService.create_experience(
        session=session, provider_id=current_user.id, obj_in=exp_in
    )


@router.put("/{id}", response_model=ExperienceRead)
async def update_experience(
    id: uuid.UUID,
    exp_in: ExperienceUpdate,
    session: SessionDep,
    current_user: User = Depends(require_provider),
) -> ExperienceRead:
    exp = await ExperienceService.get_by_id(session, id=id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    if exp.provider_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this experience"
        )

    return await ExperienceService.update_experience(
        session=session, db_obj=exp, obj_in=exp_in
    )


@router.post("/{id}/publish", response_model=ExperienceRead)
async def publish_experience(
    id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(require_provider),
) -> ExperienceRead:
    exp = await ExperienceService.get_by_id(session, id=id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    if exp.provider_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this experience"
        )

    exp.status = ExperienceStatus.PUBLISHED
    session.add(exp)
    await session.commit()
    await session.refresh(exp)
    return exp


@router.post("/{id}/unpublish", response_model=ExperienceRead)
async def unpublish_experience(
    id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(require_provider),
) -> ExperienceRead:
    exp = await ExperienceService.get_by_id(session, id=id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    if exp.provider_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this experience"
        )

    exp.status = ExperienceStatus.UNLISTED
    session.add(exp)
    await session.commit()
    await session.refresh(exp)
    return exp


@router.post("/{id}/availability", response_model=list[ExperienceAvailabilityRead])
async def add_availability(
    id: uuid.UUID,
    blocks_in: list[AvailabilityBlockCreate],
    session: SessionDep,
    current_user: User = Depends(require_provider),
) -> Sequence[ExperienceAvailabilityRead]:
    exp = await ExperienceService.get_by_id(session, id=id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    if exp.provider_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this experience"
        )

    created_blocks = []
    for block in blocks_in:
        if block.end_time <= block.start_time:
            raise HTTPException(
                status_code=422, detail="end_time must be after start_time"
            )

        db_block = ExperienceAvailability(
            experience_id=exp.id,
            date=block.date,
            start_time=block.start_time,
            end_time=block.end_time,
            price_override=block.price_override,
            is_available=block.is_available,
        )
        session.add(db_block)
        created_blocks.append(db_block)

    await session.commit()
    for b in created_blocks:
        await session.refresh(b)

    return created_blocks
