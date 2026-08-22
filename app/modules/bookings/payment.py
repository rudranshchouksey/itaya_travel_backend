from decimal import Decimal
from typing import Protocol


class PaymentFailedError(Exception):
    """Raised when a payment fails during processing."""
    pass


class PaymentGateway(Protocol):
    async def authorize(
        self, amount: Decimal, currency: str, token: str, reference: str
    ) -> str:
        """
        Authorize a payment and return a transaction ID.
        Raises PaymentFailedError on failure.
        """
        ...

    async def capture(self, transaction_id: str) -> bool:
        """
        Capture a previously authorized payment.
        """
        ...

    async def refund(self, transaction_id: str, amount: Decimal) -> bool:
        """
        Refund a payment.
        """
        ...


class MockPaymentGateway(PaymentGateway):
    """
    A mock payment gateway for testing and development.
    If the token is 'fail_token', the authorization will fail.
    """

    async def authorize(
        self, amount: Decimal, currency: str, token: str, reference: str
    ) -> str:
        if token == "fail_token":
            raise PaymentFailedError("Payment authorization failed by mock.")
        return f"mock_tx_{reference}"

    async def capture(self, transaction_id: str) -> bool:
        return True

    async def refund(self, transaction_id: str, amount: Decimal) -> bool:
        return True


# Global mock instance for now
payment_gateway = MockPaymentGateway()
