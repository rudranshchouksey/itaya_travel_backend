import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, get_current_active_user
from app.modules.trips.models import (
    Trip,
    TripItem,
    TripParticipant,
    TripParticipantRole,
)
from app.modules.trips.schemas import (
    TripCreate,
    TripItemCreate,
    TripItemRead,
    TripItemUpdate,
    TripRead,
    TripUpdate,
)
from app.modules.trips.service import TripService
from app.modules.users.models import User

router = APIRouter()


async def get_trip_owner(
    id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_active_user),
) -> Trip:
    trip = await TripService.get_trip(session, id=id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Check ownership
    participant_stmt = select(TripParticipant).where(
        TripParticipant.trip_id == id,
        TripParticipant.user_id == current_user.id,
        TripParticipant.role == TripParticipantRole.OWNER,
    )
    is_owner = (await session.execute(participant_stmt)).scalars().first()

    if not is_owner and trip.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this trip",
        )
    return trip


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
async def create_trip(
    trip_in: TripCreate,
    session: SessionDep,
    current_user: User = Depends(get_current_active_user),
) -> TripRead:
    return await TripService.create_trip(
        session=session, obj_in=trip_in, owner_id=current_user.id
    )


@router.get("", response_model=list[TripRead])
async def get_user_trips(
    session: SessionDep,
    current_user: User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 20,
) -> Sequence[TripRead]:
    return await TripService.get_user_trips(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get("/{id}", response_model=TripRead)
async def get_trip(
    trip: Trip = Depends(get_trip_owner),
) -> TripRead:
    return trip


@router.patch("/{id}", response_model=TripRead)
async def update_trip(
    trip_in: TripUpdate,
    session: SessionDep,
    trip: Trip = Depends(get_trip_owner),
) -> TripRead:
    return await TripService.update_trip(session=session, db_obj=trip, obj_in=trip_in)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    id: uuid.UUID,
    session: SessionDep,
    trip: Trip = Depends(get_trip_owner),
) -> None:
    await TripService.delete_trip(session=session, id=id)


@router.post(
    "/{id}/items", response_model=TripItemRead, status_code=status.HTTP_201_CREATED
)
async def create_trip_item(
    id: uuid.UUID,
    item_in: TripItemCreate,
    session: SessionDep,
    trip: Trip = Depends(get_trip_owner),
) -> TripItemRead:
    try:
        return await TripService.add_trip_item(
            session=session, trip_id=id, obj_in=item_in
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{id}/items/{item_id}", response_model=TripItemRead)
async def update_trip_item(
    id: uuid.UUID,
    item_id: uuid.UUID,
    item_in: TripItemUpdate,
    session: SessionDep,
    trip: Trip = Depends(get_trip_owner),
) -> TripItemRead:
    stmt = select(TripItem).where(TripItem.id == item_id, TripItem.trip_id == id)
    item = (await session.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Trip item not found")

    try:
        return await TripService.update_trip_item(
            session=session, db_obj=item, obj_in=item_in
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip_item(
    id: uuid.UUID,
    item_id: uuid.UUID,
    session: SessionDep,
    trip: Trip = Depends(get_trip_owner),
) -> None:
    stmt = select(TripItem).where(TripItem.id == item_id, TripItem.trip_id == id)
    item = (await session.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Trip item not found")

    await TripService.delete_trip_item(session=session, id=item_id)
