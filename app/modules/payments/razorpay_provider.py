"""Razorpay payment provider — isolates all Razorpay SDK interaction."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.core.config import settings


class RazorpayPaymentProvider:
    """
    Production Razorpay provider.

    All Razorpay-specific SDK calls and data transformation live here.
    The rest of the application never imports razorpay directly.
    """

    def __init__(self) -> None:
        try:
            import razorpay  # noqa: F811

            self._client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
        except ImportError:
            raise RuntimeError(
                "razorpay SDK is required. Install with: pip install razorpay"
            )

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def create_order(
        self,
        amount: int,
        currency: str,
        receipt: str,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "receipt": receipt,
        }
        if notes:
            data["notes"] = notes
        
        import razorpay.errors
        try:
            # razorpay SDK is synchronous; wrap if needed in production
            order = self._client.order.create(data=data)
            return dict(order)
        except (razorpay.errors.ServerError, razorpay.errors.GatewayError) as e:
            raise TransientRetryError(str(e)) from e

    async def verify_payment(
        self,
        payment_id: str,
        order_id: str,
        signature: str,
    ) -> bool:
        try:
            self._client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            return True
        except Exception:
            return False

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
    ) -> dict[str, Any]:
        import razorpay.errors
        try:
            result = self._client.payment.capture(payment_id, amount)
            return dict(result)
        except (razorpay.errors.ServerError, razorpay.errors.GatewayError) as e:
            raise TransientRetryError(str(e)) from e

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def fetch_payment(
        self,
        payment_id: str,
    ) -> dict[str, Any]:
        import razorpay.errors
        try:
            result = self._client.payment.fetch(payment_id)
            return dict(result)
        except (razorpay.errors.ServerError, razorpay.errors.GatewayError) as e:
            raise TransientRetryError(str(e)) from e

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def refund_payment(
        self,
        payment_id: str,
        amount: int,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import razorpay.errors
        data: dict[str, Any] = {"amount": amount}
        if notes:
            data["notes"] = notes
        try:
            result = self._client.payment.refund(payment_id, amount, data)
            return dict(result)
        except (razorpay.errors.ServerError, razorpay.errors.GatewayError) as e:
            raise TransientRetryError(str(e)) from e

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
