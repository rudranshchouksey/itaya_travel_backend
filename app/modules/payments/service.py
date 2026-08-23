import uuid
from datetime import UTC, datetime
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
    BookingStatus,
    validate_booking_transition,
)
from app.modules.payments.currency import (
    get_currency_rate_provider,
    resolve_display_currency,
)
from app.modules.payments.mock_provider import payment_provider
from app.modules.payments.models import (
    Payment,
    PaymentStatus,
    ProviderTransaction,
    Refund,
    RefundStatus,
    TransactionStatus,
    TransactionType,
    WebhookEvent,
    validate_payment_transition,
)
from app.modules.payments.schemas import PaymentCreateResponse


class FinancialService:
    @staticmethod
    async def record_booking_financials(
        session: AsyncSession, booking: Booking
    ) -> None:
        """Record the provider credit and platform fee for a booking."""
        for item in booking.items:
            if not item.provider_id:
                continue

            item_amount = item.subtotal or item.total
            commission_rate = Decimal(str(settings.PLATFORM_COMMISSION_RATE))
            item_fee = (item_amount * commission_rate).quantize(Decimal("0.01"))

            # 1. Credit provider for item subtotal/total
            credit_tx = ProviderTransaction(
                provider_id=item.provider_id,
                booking_id=booking.id,
                booking_item_id=item.id,
                amount=item_amount,
                currency=booking.currency,
                transaction_type=TransactionType.BOOKING_CREDIT,
                status=TransactionStatus.COMPLETED,
                reference=f"Booking Credit for {booking.reference}",
            )
            session.add(credit_tx)

            # 2. Platform commission deduction
            if item_fee > Decimal("0.00"):
                fee_tx = ProviderTransaction(
                    provider_id=item.provider_id,
                    booking_id=booking.id,
                    booking_item_id=item.id,
                    amount=-item_fee,
                    currency=booking.currency,
                    transaction_type=TransactionType.PLATFORM_FEE,
                    status=TransactionStatus.COMPLETED,
                    reference=f"Platform Fee for {booking.reference}",
                )
                session.add(fee_tx)

    @staticmethod
    async def record_refund_financials(
        session: AsyncSession,
        refund: Refund,
        booking: Booking,
        payment: Payment | None = None,
    ) -> None:
        """Record the reversal of financials due to a refund."""
        if not booking.items:
            return

        # Find the provider(s) associated with this booking
        # Apportion refund across items/providers or assign to the first provider
        provider_ids = [item.provider_id for item in booking.items if item.provider_id]
        if not provider_ids:
            return

        # Simple single/first provider allocation
        provider_id = provider_ids[0]

        # Calculate the refund amount in the booking's base currency
        refund_booking_amount = refund.amount
        if refund.currency != booking.currency and payment and payment.amount > 0:
            proportion = refund.amount / payment.amount
            refund_booking_amount = (booking.total * proportion).quantize(
                Decimal("0.01")
            )
        elif refund.currency != booking.currency and not payment:
            # Fallback if payment is not provided (should not happen with updated call)
            refund_booking_amount = booking.total

        refund_tx = ProviderTransaction(
            provider_id=provider_id,
            booking_id=booking.id,
            amount=-refund_booking_amount,
            currency=booking.currency,
            transaction_type=TransactionType.REFUND,
            status=TransactionStatus.COMPLETED,
            reference=f"Refund Reversal: {refund.id}",
        )
        session.add(refund_tx)

    @staticmethod
    async def get_provider_balance(
        session: AsyncSession, provider_id: uuid.UUID
    ) -> Decimal:
        stmt = select(ProviderTransaction).where(
            ProviderTransaction.provider_id == provider_id,
            ProviderTransaction.status == TransactionStatus.COMPLETED,
        )
        transactions = (await session.execute(stmt)).scalars().all()
        return sum((tx.amount for tx in transactions), Decimal("0.00"))


class PaymentService:
    @staticmethod
    async def create_payment(
        session: AsyncSession,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        idempotency_key: str | None = None,
        user_currency: str | None = None,
        client_locale: str | None = None,
        client_country: str | None = None,
    ) -> PaymentCreateResponse:
        # Check idempotency
        if idempotency_key:
            stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
            existing_payment = (await session.execute(stmt)).scalar_one_or_none()
            if existing_payment:
                if existing_payment.provider_order_id:
                    return PaymentCreateResponse(
                        payment_id=existing_payment.id,
                        provider_order_id=existing_payment.provider_order_id,
                        amount=existing_payment.amount,
                        currency=existing_payment.currency,
                        key_id=settings.RAZORPAY_KEY_ID or "mock_key_id",
                    )

        stmt = (
            select(Booking)
            .options(selectinload(Booking.items))
            .where(Booking.id == booking_id)
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()

        if not booking:
            raise NotFoundError("Booking not found")
        if booking.user_id != user_id:
            raise PermissionDeniedError(
                "Cannot create payment for another user's booking"
            )

        if booking.booking_status not in [
            BookingStatus.PAYMENT_PENDING,
            BookingStatus.PENDING,
        ]:
            raise ValidationError(
                f"Booking is not in payable state. Current: {booking.booking_status}"
            )

        amount_minor = int(booking.total * 100)

        # 1. Resolve Display/Transaction Currency
        transaction_currency = resolve_display_currency(
            user_explicit_currency=user_currency,
            client_locale=client_locale,
            client_country=client_country,
        )

        # 2. Convert Amount if needed
        transaction_amount = booking.total
        if transaction_currency != booking.currency:
            rate_provider = get_currency_rate_provider()
            exchange_rate = await rate_provider.get_exchange_rate(
                from_currency=booking.currency, to_currency=transaction_currency
            )
            transaction_amount = (booking.total * exchange_rate).quantize(
                Decimal("0.01")
            )

        if transaction_amount <= 0:
            raise ValidationError(
                "Calculated payment amount must be greater than zero."
            )

        # Stripe API mostly expects smallest currency unit, except for zero-decimal currencies
        zero_decimal_currencies = {
            "JPY",
            "BIF",
            "CLP",
            "PYG",
            "VUV",
            "XAF",
            "XOF",
            "XPF",
        }
        if transaction_currency in zero_decimal_currencies:
            amount_minor = int(transaction_amount)
        else:
            amount_minor = int(transaction_amount * 100)

        # Create Provider Order
        order_data = await payment_provider.create_order(
            amount=amount_minor,
            currency=transaction_currency,
            receipt=str(booking.id),
        )

        payment = Payment(
            booking_id=booking.id,
            provider=settings.PAYMENT_PROVIDER,
            provider_order_id=order_data.get("id"),
            amount=transaction_amount,
            currency=transaction_currency,
            status=PaymentStatus.CREATED,
            idempotency_key=idempotency_key,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)

        return PaymentCreateResponse(
            payment_id=payment.id,
            provider_order_id=payment.provider_order_id or "",
            amount=payment.amount,
            currency=payment.currency,
            key_id=settings.RAZORPAY_KEY_ID or "mock_key_id",
        )

    @staticmethod
    async def get_payment(
        session: AsyncSession,
        payment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Payment:
        stmt = (
            select(Payment)
            .options(selectinload(Payment.booking))
            .where(Payment.id == payment_id)
        )
        payment = (await session.execute(stmt)).scalar_one_or_none()
        if not payment:
            raise NotFoundError("Payment not found")
        if payment.booking.user_id != user_id:
            raise PermissionDeniedError("Unauthorized")
        return payment

    @staticmethod
    async def verify_payment(
        session: AsyncSession,
        payment_id: uuid.UUID,
        provider_payment_id: str,
        provider_order_id: str,
        provider_signature: str,
        user_id: uuid.UUID,
    ) -> Payment:
        stmt = select(Payment).where(Payment.id == payment_id)
        payment = (await session.execute(stmt)).scalar_one_or_none()
        if not payment:
            raise NotFoundError("Payment not found")

        stmt = (
            select(Booking)
            .options(selectinload(Booking.items))
            .where(Booking.id == payment.booking_id)
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()
        if not booking or booking.user_id != user_id:
            raise PermissionDeniedError("Unauthorized")

        is_valid = await payment_provider.verify_payment(
            provider_payment_id, provider_order_id, provider_signature
        )

        if not is_valid:
            payment.status = PaymentStatus.FAILED
            payment.failure_message = "Signature verification failed"
            await session.commit()
            raise ValidationError("Payment signature verification failed")

        if not validate_payment_transition(payment.status, PaymentStatus.CAPTURED):
            # If already captured (e.g. via webhook or idempotent call), just return
            if payment.status == PaymentStatus.CAPTURED:
                return payment
            raise ValidationError("Invalid payment state transition")

        payment.provider_payment_id = provider_payment_id
        payment.status = PaymentStatus.CAPTURED
        payment.captured_at = datetime.now(UTC)

        # Confirm booking
        if validate_booking_transition(booking.booking_status, BookingStatus.CONFIRMED):
            booking.booking_status = BookingStatus.CONFIRMED
            await FinancialService.record_booking_financials(session, booking)

        await session.commit()
        await session.refresh(payment)
        return payment

    @staticmethod
    async def create_refund(
        session: AsyncSession,
        payment_id: uuid.UUID,
        amount: Decimal | None,
        reason: str | None,
        idempotency_key: str | None = None,
    ) -> Refund:
        if idempotency_key:
            stmt = select(Refund).where(Refund.idempotency_key == idempotency_key)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        stmt = select(Payment).where(Payment.id == payment_id)
        payment = (await session.execute(stmt)).scalar_one_or_none()

        if not payment:
            raise NotFoundError("Payment not found")

        if payment.status not in [
            PaymentStatus.CAPTURED,
            PaymentStatus.PARTIALLY_REFUNDED,
        ]:
            raise ValidationError("Payment must be captured to be refunded")

        refund_amount = amount if amount is not None else payment.amount
        if refund_amount <= 0:
            raise ValidationError("Refund amount must be positive")

        # Check against already refunded amount
        stmt_refunds = select(Refund).where(
            Refund.payment_id == payment_id,
            Refund.status == RefundStatus.COMPLETED,
        )
        existing_refunds = (await session.execute(stmt_refunds)).scalars().all()
        total_refunded = sum((r.amount for r in existing_refunds), Decimal("0.00"))

        if total_refunded + refund_amount > payment.amount:
            raise ValidationError("Refund amount exceeds captured amount")

        # Create Refund via Provider
        amount_minor = int(refund_amount * 100)
        provider_refund = await payment_provider.refund_payment(
            payment.provider_payment_id or "",
            amount=amount_minor,
            notes={"reason": reason} if reason else None,
        )

        refund = Refund(
            payment_id=payment.id,
            booking_id=payment.booking_id,
            provider_refund_id=provider_refund.get("id"),
            amount=refund_amount,
            currency=payment.currency,
            reason=reason,
            status=RefundStatus.COMPLETED,
            idempotency_key=idempotency_key,
        )
        session.add(refund)

        # Update Payment Status
        new_total_refunded = total_refunded + refund_amount
        if new_total_refunded >= payment.amount:
            payment.status = PaymentStatus.REFUNDED
        else:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED

        # Update Booking Status if full or partial refund (unless already cancelled)
        stmt = (
            select(Booking)
            .options(selectinload(Booking.items))
            .where(Booking.id == payment.booking_id)
        )
        booking = (await session.execute(stmt)).scalar_one_or_none()
        if booking:
            if booking.booking_status != BookingStatus.CANCELLED:
                if new_total_refunded >= payment.amount:
                    if validate_booking_transition(
                        booking.booking_status, BookingStatus.REFUNDED
                    ):
                        booking.booking_status = BookingStatus.REFUNDED
                else:
                    if validate_booking_transition(
                        booking.booking_status, BookingStatus.PARTIALLY_REFUNDED
                    ):
                        booking.booking_status = BookingStatus.PARTIALLY_REFUNDED

            await FinancialService.record_refund_financials(
                session, refund, booking, payment
            )

        await session.commit()
        await session.refresh(refund)
        return refund

    @staticmethod
    async def process_webhook(
        session: AsyncSession,
        provider: str,
        payload: dict,
        signature: str,
        body: bytes,
    ) -> None:
        if not payment_provider.verify_webhook_signature(body, signature):
            raise ValidationError("Invalid webhook signature")

        event_id = payload.get("id") or payload.get("event_id")
        if not event_id:
            raise ValidationError("Webhook missing event ID")

        # Check idempotency
        stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return  # Already processed

        event_type = payload.get("event")
        webhook_event = WebhookEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type or "unknown",
            payload=payload,
            processed=True,
        )
        session.add(webhook_event)

        # Process payment events
        order_id = None
        payment_id_str = None
        is_captured = False

        if provider == "razorpay":
            if event_type in ["payment.captured", "order.paid"]:
                payment_entity = (
                    payload.get("payload", {}).get("payment", {}).get("entity", {})
                )
                order_id = payment_entity.get("order_id") or payload.get(
                    "payload", {}
                ).get("order", {}).get("entity", {}).get("id")
                payment_id_str = payment_entity.get("id")
                is_captured = True
        elif provider == "stripe":
            if event_type == "payment_intent.succeeded":
                payment_intent = payload.get("data", {}).get("object", {})
                payment_id_str = payment_intent.get("id")
                # We stored our internal booking ID or payment reference in metadata or receipt,
                # but we also have provider_order_id in our DB as the PaymentIntent ID.
                # So order_id for Stripe IS the payment_id_str.
                order_id = payment_id_str
                is_captured = True

        if is_captured and order_id:
            stmt_p = (
                select(Payment)
                .options(selectinload(Payment.booking).selectinload(Booking.items))
                .where(Payment.provider_order_id == order_id)
            )
            payment = (await session.execute(stmt_p)).scalar_one_or_none()
            if payment and payment.status != PaymentStatus.CAPTURED:
                payment.status = PaymentStatus.CAPTURED
                payment.provider_payment_id = payment_id_str
                payment.captured_at = datetime.now(UTC)
                if payment.booking and validate_booking_transition(
                    payment.booking.booking_status, BookingStatus.CONFIRMED
                ):
                    payment.booking.booking_status = BookingStatus.CONFIRMED
                    await FinancialService.record_booking_financials(
                        session, payment.booking
                    )

        await session.commit()
