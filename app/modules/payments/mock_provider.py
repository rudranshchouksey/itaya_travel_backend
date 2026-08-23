"""Mock payment provider — testing and development fallback."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

from app.core.config import settings


class MockPaymentProvider:
    """
    Mock payment provider for local development and testing.

    If the payment_id is 'fail_token' or starts with 'fail_', the verification
    will fail.
    """

    async def create_order(
        self,
        amount: int,
        currency: str,
        receipt: str,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": f"mock_order_{uuid.uuid4().hex[:8]}",
            "entity": "order",
            "amount": amount,
            "amount_paid": 0,
            "amount_due": amount,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
            "notes": notes or {},
        }

    async def verify_payment(
        self,
        payment_id: str,
        order_id: str,
        signature: str,
    ) -> bool:
        if payment_id == "fail_token" or payment_id.startswith("fail_"):
            return False
        return True

    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
    ) -> dict[str, Any]:
        return {
            "id": payment_id,
            "entity": "payment",
            "amount": amount,
            "currency": "INR",
            "status": "captured",
        }

    async def fetch_payment(
        self,
        payment_id: str,
    ) -> dict[str, Any]:
        return {
            "id": payment_id,
            "entity": "payment",
            "amount": 1000,
            "currency": "INR",
            "status": "captured",
        }

    async def refund_payment(
        self,
        payment_id: str,
        amount: int,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": f"mock_rfnd_{uuid.uuid4().hex[:8]}",
            "entity": "refund",
            "amount": amount,
            "payment_id": payment_id,
            "status": "processed",
        }

    def verify_webhook_signature(
        self,
        body: str | bytes,
        signature: str,
    ) -> bool:
        if isinstance(body, str):
            body = body.encode("utf-8")
        secret = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


def get_payment_provider() -> Any:
    """Factory to return the appropriate payment provider."""
    if settings.PAYMENT_PROVIDER.lower() == "razorpay":
        from app.modules.payments.razorpay_provider import RazorpayPaymentProvider

        return RazorpayPaymentProvider()
    elif settings.PAYMENT_PROVIDER.lower() == "stripe":
        from app.modules.payments.stripe_provider import StripePaymentProvider

        return StripePaymentProvider()
    else:
        return MockPaymentProvider()


# Global provider instance
payment_provider = get_payment_provider()
