"""Payment provider interface — abstract contract for all payment providers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PaymentProviderInterface(Protocol):
    """
    Abstract interface for payment providers.

    All monetary amounts are in the **smallest currency unit** (e.g. paise for INR,
    cents for USD) as integers, matching Razorpay's convention. The service layer
    converts Decimal amounts before calling provider methods.
    """

    async def create_order(
        self,
        amount: int,
        currency: str,
        receipt: str,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an order/payment intent. Returns provider-specific order data."""
        ...

    async def verify_payment(
        self,
        payment_id: str,
        order_id: str,
        signature: str,
    ) -> bool:
        """Verify the payment signature. Returns True if valid."""
        ...

    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
    ) -> dict[str, Any]:
        """Capture a previously authorised payment. Returns provider response."""
        ...

    async def fetch_payment(
        self,
        payment_id: str,
    ) -> dict[str, Any]:
        """Fetch payment details from the provider."""
        ...

    async def refund_payment(
        self,
        payment_id: str,
        amount: int,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a refund. Returns provider-specific refund data."""
        ...

    def verify_webhook_signature(
        self,
        body: str | bytes,
        signature: str,
    ) -> bool:
        """Verify webhook signature. Returns True if valid."""
        ...


def amount_to_smallest_unit(amount: Decimal, currency: str) -> int:
    """Convert a Decimal amount to the smallest currency unit (paise/cents)."""
    # INR, USD, EUR etc. all use 2 decimal places
    return int(amount * 100)


def amount_from_smallest_unit(amount_minor: int, currency: str) -> Decimal:
    """Convert from smallest currency unit back to Decimal."""
    return Decimal(amount_minor) / Decimal(100)
