"""Stripe payment provider — isolates all Stripe SDK interaction."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.retry import TransientRetryError, with_backoff

logger = logging.getLogger(__name__)


class StripePaymentProvider:
    """
    Production Stripe provider.
    All Stripe-specific SDK calls and data transformation live here.
    """

    def __init__(self) -> None:
        try:
            import stripe  # noqa: F811
        except ImportError:
            raise RuntimeError(
                "stripe SDK is required. Install with: pip install stripe"
            )

        # Configure stripe api key
        stripe.api_key = settings.STRIPE_SECRET_KEY

    # Only retry transient errors
    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def create_order(
        self,
        amount: int,
        currency: str,
        receipt: str,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a PaymentIntent.
        `receipt` is used as idempotency key to prevent duplicate charges.
        """
        import stripe

        # Override the retry logic to only catch transient Stripe errors
        try:
            # Stripe uses smallest currency unit for most currencies
            # Exceptions exist (e.g. JPY has zero decimal), but our provider interface
            # assumes `amount` is already appropriately scaled.

            # Idempotency key from receipt
            idempotency_key = receipt

            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency.lower(),
                metadata={"receipt": receipt, **(notes or {})},
                idempotency_key=idempotency_key,
            )

            return {
                "id": intent.id,
                "entity": "order",
                "amount": intent.amount,
                "amount_paid": intent.amount_received,
                "amount_due": intent.amount - intent.amount_received,
                "currency": intent.currency.upper(),
                "receipt": receipt,
                "status": "created",
                "notes": intent.metadata,
                "client_secret": intent.client_secret,
            }
        except (stripe.error.RateLimitError, stripe.error.APIConnectionError) as e:
            # Re-raise as TransientRetryError to trigger backoff
            raise TransientRetryError(str(e)) from e
        except stripe.error.StripeError as e:
            # 5xx errors are retryable
            if getattr(e, "http_status", 0) and e.http_status >= 500:
                raise TransientRetryError(str(e)) from e
            logger.error(f"Permanent Stripe error during create_order: {e}")
            raise RuntimeError(f"Payment intent creation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during create_order: {e}")
            raise RuntimeError(f"Payment intent creation failed: {str(e)}")

    async def verify_payment(
        self,
        payment_id: str,
        order_id: str,
        signature: str,
    ) -> bool:
        """
        For Stripe, verification is typically done via Webhooks or fetching the intent.
        The client passes the PaymentIntent ID as order_id/payment_id.
        """
        # A simple retrieval to check if it succeeded
        payment = await self.fetch_payment(payment_id=order_id)
        return payment["status"] == "captured"

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
    ) -> dict[str, Any]:
        import stripe

        try:
            intent = stripe.PaymentIntent.capture(payment_id, amount_to_capture=amount)
            return {
                "id": intent.id,
                "entity": "payment",
                "amount": intent.amount,
                "currency": intent.currency.upper(),
                "status": "captured" if intent.status == "succeeded" else intent.status,
            }
        except (stripe.error.RateLimitError, stripe.error.APIConnectionError) as e:
            raise TransientRetryError(str(e)) from e
        except stripe.error.StripeError as e:
            if getattr(e, "http_status", 0) and e.http_status >= 500:
                raise TransientRetryError(str(e)) from e
            raise RuntimeError(f"Payment capture failed: {str(e)}")

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def fetch_payment(
        self,
        payment_id: str,
    ) -> dict[str, Any]:
        import stripe

        try:
            intent = stripe.PaymentIntent.retrieve(payment_id)
            return {
                "id": intent.id,
                "entity": "payment",
                "amount": intent.amount,
                "currency": intent.currency.upper(),
                "status": "captured" if intent.status == "succeeded" else intent.status,
            }
        except (stripe.error.RateLimitError, stripe.error.APIConnectionError) as e:
            raise TransientRetryError(str(e)) from e
        except stripe.error.StripeError as e:
            if getattr(e, "http_status", 0) and e.http_status >= 500:
                raise TransientRetryError(str(e)) from e
            raise RuntimeError(f"Payment fetch failed: {str(e)}")

    @with_backoff(retryable_exceptions=(TransientRetryError,))
    async def refund_payment(
        self,
        payment_id: str,
        amount: int,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import stripe

        try:
            # We use a unique idempotency key based on payment_id + amount + a unique part from notes if present
            # Or ideally from the backend refund ID if passed in notes
            refund_ref = (notes or {}).get("refund_id", f"{payment_id}_{amount}")
            idempotency_key = f"rfnd_{refund_ref}"

            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=amount,
                metadata=notes,
                idempotency_key=idempotency_key,
            )
            return {
                "id": refund.id,
                "entity": "refund",
                "amount": refund.amount,
                "payment_id": payment_id,
                "status": "processed"
                if refund.status == "succeeded"
                else refund.status,
            }
        except (stripe.error.RateLimitError, stripe.error.APIConnectionError) as e:
            raise e
        except stripe.error.StripeError as e:
            if e.http_status and e.http_status >= 500:
                raise e
            logger.error(f"Permanent Stripe error during refund: {e}")
            raise RuntimeError(f"Refund failed: {str(e)}")

    def verify_webhook_signature(
        self,
        body: str | bytes,
        signature: str,
    ) -> bool:
        import stripe

        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            # Stripe Python SDK verifies signature and returns the event
            # Since this interface just returns a boolean, we'll verify it here
            stripe.Webhook.Signature.verify_header(body, signature, webhook_secret)
            return True
        except stripe.error.SignatureVerificationError:
            return False
