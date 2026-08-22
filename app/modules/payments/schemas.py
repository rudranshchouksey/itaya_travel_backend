import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.models import PaymentStatus, RefundStatus


class PaymentCreateRequest(BaseModel):
    booking_id: uuid.UUID
    idempotency_key: str | None = None


class PaymentCreateResponse(BaseModel):
    payment_id: uuid.UUID
    provider_order_id: str
    amount: Decimal
    currency: str
    key_id: str


class PaymentVerifyRequest(BaseModel):
    payment_id: str
    provider_payment_id: str
    provider_order_id: str
    provider_signature: str


class PaymentRead(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    provider: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    captured_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RefundCreateRequest(BaseModel):
    payment_id: uuid.UUID
    amount: Decimal | None = Field(
        None, description="Amount to refund. If None, full amount is refunded."
    )
    reason: str | None = None
    idempotency_key: str | None = None


class RefundRead(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    currency: str
    status: RefundStatus
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CancellationRequest(BaseModel):
    reason: str | None = None
