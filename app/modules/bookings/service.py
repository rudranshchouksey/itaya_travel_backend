import secrets
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.modules.bookings.models import (
    Booking,
    BookingGuest,
    BookingItem,
    BookingStatus,
    validate_booking_transition,
)
from app.modules.bookings.schemas import BookingCreate
from app.modules.experiences.models import Experience, ExperienceAvailability
from app.modules.listings.models import Listing, ListingAvailability
from app.modules.payments.models import PaymentStatus
from app.modules.payments.service import PaymentService
from app.modules.trips.models import TripItemType


class BookingService:
    @staticmethod
    async def create_booking(
        session: AsyncSession,
        user_id: uuid.UUID,
        booking_in: BookingCreate,
        idempotency_key: str | None = None,
    ) -> Booking:
        # Check idempotency
        if idempotency_key:
            stmt = (
                select(Booking)
                .options(
                    selectinload(Booking.items),
                    selectinload(Booking.guests),
                    selectinload(Booking.payments),
                )
                .where(Booking.idempotency_key == idempotency_key)
                .where(Booking.user_id == user_id)
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        reference = f"BKG-{secrets.token_hex(4).upper()}"

        booking_db = Booking(
            user_id=user_id,
            trip_id=booking_in.trip_id,
            reference=reference,
            idempotency_key=idempotency_key,
            currency=booking_in.currency,
            subtotal=Decimal("0.00"),
            fees=Decimal("0.00"),
            platform_fee=Decimal("0.00"),
            provider_amount=Decimal("0.00"),
            taxes=Decimal("0.00"),
            discounts=Decimal("0.00"),
            total=Decimal("0.00"),
            booking_status=BookingStatus.PAYMENT_PENDING,
        )

        for guest_in in booking_in.guests:
            guest_db = BookingGuest(
                first_name=guest_in.first_name,
                last_name=guest_in.last_name,
                email=guest_in.email,
                is_primary=guest_in.is_primary,
            )
            booking_db.guests.append(guest_db)

        # Process Items
        for item_in in booking_in.items:
            item_db = BookingItem(
                item_type=item_in.item_type,
                listing_id=item_in.listing_id,
                experience_id=item_in.experience_id,
                start_date=item_in.start_date,
                end_date=item_in.end_date,
                start_time=item_in.start_time,
                end_time=item_in.end_time,
                quantity=item_in.quantity,
                guest_count=item_in.guest_count,
                taxes=Decimal("0.00"),
                fees=Decimal("0.00"),
            )

            if item_in.item_type == TripItemType.STAY:
                # Validate listing and availability
                stmt = select(Listing).where(Listing.id == item_in.listing_id)
                listing = (await session.execute(stmt)).scalar_one_or_none()
                if not listing:
                    raise NotFoundError(f"Listing {item_in.listing_id} not found")

                if listing.guest_capacity < item_in.guest_count:
                    raise ValidationError("Guest count exceeds listing capacity")

                item_db.provider_id = listing.host_id

                # Lock availabilities
                avail_stmt = (
                    select(ListingAvailability)
                    .where(ListingAvailability.listing_id == item_in.listing_id)
                    .where(ListingAvailability.date >= item_in.start_date)
                    .where(ListingAvailability.date < item_in.end_date)
                    .with_for_update()
                )
                availabilities = (await session.execute(avail_stmt)).scalars().all()

                # Check if all dates are available
                num_days = (item_in.end_date - item_in.start_date).days
                if len(availabilities) != num_days:
                    raise ValidationError("Not all dates are available or configured")

                total_price = Decimal("0.00")
                for avail in availabilities:
                    if not avail.is_available:
                        raise ValidationError(f"Date {avail.date} is not available")
                    total_price += avail.price
                    # Deduct availability
                    avail.is_available = False

                item_db.price_snapshot = total_price
                item_db.subtotal = total_price * item_in.quantity
                item_db.total = item_db.subtotal + item_db.fees + item_db.taxes

            elif item_in.item_type == TripItemType.EXPERIENCE:
                stmt = select(Experience).where(Experience.id == item_in.experience_id)
                exp = (await session.execute(stmt)).scalar_one_or_none()
                if not exp:
                    raise NotFoundError(f"Experience {item_in.experience_id} not found")

                if exp.guest_capacity < item_in.guest_count:
                    raise ValidationError("Guest count exceeds experience capacity")

                item_db.provider_id = exp.provider_id

                avail_stmt = (
                    select(ExperienceAvailability)
                    .where(
                        ExperienceAvailability.experience_id == item_in.experience_id
                    )
                    .where(ExperienceAvailability.date == item_in.start_date)
                    .where(ExperienceAvailability.start_time == item_in.start_time)
                    .with_for_update()
                )
                avail = (await session.execute(avail_stmt)).scalar_one_or_none()
                if not avail:
                    raise ValidationError(
                        "Experience availability not found for this time"
                    )

                if not avail.is_available:
                    raise ValidationError("Experience is fully booked for this time")

                price = (
                    avail.price_override
                    if avail.price_override is not None
                    else exp.base_price
                )
                item_db.price_snapshot = price
                item_db.subtotal = price * item_in.quantity
                item_db.total = item_db.subtotal + item_db.fees + item_db.taxes

                avail.is_available = False

            booking_db.items.append(item_db)
            booking_db.subtotal += item_db.subtotal

        # Set totals and platform commission
        commission_rate = Decimal(str(settings.PLATFORM_COMMISSION_RATE))
        booking_db.platform_fee = (booking_db.subtotal * commission_rate).quantize(
            Decimal("0.01")
        )
        booking_db.total = (
            booking_db.subtotal
            + booking_db.fees
            + booking_db.taxes
            - booking_db.discounts
        )
        booking_db.provider_amount = booking_db.total - booking_db.platform_fee

        session.add(booking_db)
        await session.commit()

        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.items),
                selectinload(Booking.guests),
                selectinload(Booking.payments),
            )
            .where(Booking.id == booking_db.id)
        )
        return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def get_booking(
        session: AsyncSession, booking_id: uuid.UUID, user_id: uuid.UUID
    ) -> Booking:
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.items),
                selectinload(Booking.guests),
                selectinload(Booking.payments),
            )
            .where(Booking.id == booking_id)
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()

        if not booking:
            raise NotFoundError("Booking not found")

        if booking.user_id != user_id:
            raise PermissionDeniedError(
                "You do not have permission to view this booking"
            )

        return booking

    @staticmethod
    async def get_user_bookings(
        session: AsyncSession, user_id: uuid.UUID
    ) -> list[Booking]:
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.items),
                selectinload(Booking.guests),
                selectinload(Booking.payments),
            )
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def cancel_booking(
        session: AsyncSession,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> Booking:
        booking = await BookingService.get_booking(session, booking_id, user_id)

        if not validate_booking_transition(
            booking.booking_status, BookingStatus.CANCELLED
        ):
            raise ValidationError(
                f"Cannot cancel a booking in {booking.booking_status} state"
            )

        was_confirmed = booking.booking_status == BookingStatus.CONFIRMED
        booking.booking_status = BookingStatus.CANCELLED
        booking.cancellation_reason = reason
        booking.cancelled_at = date.today()

        # Check if there is a captured payment to refund based on cancellation policy
        if was_confirmed and booking.payments:
            captured_payments = [
                p for p in booking.payments if p.status == PaymentStatus.CAPTURED
            ]
            if captured_payments:
                payment = captured_payments[0]
                # Cancellation policy:
                # Earliest checkin date
                start_dates = [
                    item.start_date for item in booking.items if item.start_date
                ]
                today = date.today()
                refund_pct = Decimal("1.0")  # Default full refund
                if start_dates:
                    earliest_date = min(start_dates)
                    days_diff = (earliest_date - today).days
                    if days_diff >= 2:
                        refund_pct = Decimal("1.0")  # 100% refund
                    elif days_diff >= 1:
                        refund_pct = Decimal("0.5")  # 50% refund
                    else:
                        refund_pct = Decimal("0.0")  # No refund

                refund_amount = (payment.amount * refund_pct).quantize(Decimal("0.01"))
                if refund_amount > Decimal("0.00"):
                    await PaymentService.create_refund(
                        session=session,
                        payment_id=payment.id,
                        amount=refund_amount,
                        reason=reason or "Booking cancelled",
                    )

        # Free up availability
        for item in booking.items:
            if item.item_type == TripItemType.STAY:
                avail_stmt = (
                    select(ListingAvailability)
                    .where(ListingAvailability.listing_id == item.listing_id)
                    .where(ListingAvailability.date >= item.start_date)
                    .where(ListingAvailability.date < item.end_date)
                )
                availabilities = (await session.execute(avail_stmt)).scalars().all()
                for avail in availabilities:
                    avail.is_available = True

            elif item.item_type == TripItemType.EXPERIENCE:
                avail_stmt = (
                    select(ExperienceAvailability)
                    .where(ExperienceAvailability.experience_id == item.experience_id)
                    .where(ExperienceAvailability.date == item.start_date)
                    .where(ExperienceAvailability.start_time == item.start_time)
                )
                avail = (await session.execute(avail_stmt)).scalar_one_or_none()
                if avail:
                    avail.is_available = True

        session.add(booking)
        await session.commit()

        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.items),
                selectinload(Booking.guests),
                selectinload(Booking.payments),
            )
            .where(Booking.id == booking.id)
        )
        return (await session.execute(stmt)).scalar_one()
