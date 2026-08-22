"""Payment domain models — Payment, Refund, WebhookEvent, ProviderTransaction."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel as Base

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


PAYMENT_STATUS_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.CREATED: {
        PaymentStatus.PENDING,
        PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.PENDING: {
        PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.AUTHORIZED: {
        PaymentStatus.CAPTURED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.CAPTURED: {
        PaymentStatus.REFUNDED,
        PaymentStatus.PARTIALLY_REFUNDED,
    },
    PaymentStatus.FAILED: set(),
    PaymentStatus.CANCELLED: set(),
    PaymentStatus.REFUNDED: set(),
    PaymentStatus.PARTIALLY_REFUNDED: {PaymentStatus.REFUNDED},
}


def validate_payment_transition(current: PaymentStatus, target: PaymentStatus) -> bool:
    """Return True if the transition is valid."""
    return target in PAYMENT_STATUS_TRANSITIONS.get(current, set())


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionType(str, enum.Enum):
    BOOKING_CREDIT = "booking_credit"
    PLATFORM_FEE = "platform_fee"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    PAYOUT_PENDING = "payout_pending"
    PAYOUT_COMPLETED = "payout_completed"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REVERSED = "reversed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Payment(Base):
    __tablename__ = "payments"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True
    )
    provider_order_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum", create_type=False),
        default=PaymentStatus.CREATED,
        nullable=False,
        index=True,
    )
    payment_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    booking = relationship("Booking", back_populates="payments")
    refunds: Mapped[list["Refund"]] = relationship(
        "Refund",
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class Refund(Base):
    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_refund_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status_enum"),
        default=RefundStatus.PENDING,
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="refunds")
    booking = relationship("Booking")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str] = mapped_column(
        String(200), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProviderTransaction(Base):
    __tablename__ = "provider_transactions"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    booking_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booking_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type_enum"),
        nullable=False,
        index=True,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status_enum"),
        default=TransactionStatus.PENDING,
        nullable=False,
    )
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
