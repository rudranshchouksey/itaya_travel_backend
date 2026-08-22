import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.api.deps import SessionDep, get_current_active_user
from app.modules.bookings.schemas import BookingCreate, BookingRead
from app.modules.bookings.service import BookingService
from app.modules.users.models import User

router = APIRouter(tags=["Bookings"])


@router.post(
    "",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
)
async def create_booking(
    booking_in: BookingCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    payment_token: Annotated[str | None, Header(alias="X-Payment-Token")] = None,
):
    """
    Create a new booking for a stay or an experience.
    Pass an `Idempotency-Key` header to safely retry requests without double-booking.
    Pass an `X-Payment-Token` header for payment processing.
    """
    return await BookingService.create_booking(
        session=session,
        user_id=current_user.id,
        booking_in=booking_in,
        idempotency_key=idempotency_key,
        payment_token=payment_token,
    )


@router.get(
    "",
    response_model=list[BookingRead],
    summary="Get user bookings",
)
async def get_bookings(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Retrieve all bookings made by the authenticated user.
    """
    return await BookingService.get_user_bookings(session, current_user.id)


@router.get(
    "/{booking_id}",
    response_model=BookingRead,
    summary="Get a specific booking",
)
async def get_booking(
    booking_id: uuid.UUID,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Retrieve a specific booking by ID. Must be owned by the user.
    """
    return await BookingService.get_booking(session, booking_id, current_user.id)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingRead,
    summary="Cancel a booking",
)
async def cancel_booking(
    booking_id: uuid.UUID,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Cancel a booking and free up the associated availability.
    """
    return await BookingService.cancel_booking(session, booking_id, current_user.id)
