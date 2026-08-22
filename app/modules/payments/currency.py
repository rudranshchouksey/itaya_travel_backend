from decimal import Decimal
from typing import Any, Protocol

from app.core.config import settings


class CurrencyRateProvider(Protocol):
    """Protocol for fetching currency exchange rates."""

    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Get the exchange rate multiplier to convert from one currency to another."""
        ...


class MockCurrencyRateProvider:
    """Mock implementation of exchange rates for testing and development."""

    # Deterministic mocked exchange rates relative to USD
    # These are fixed for idempotent testing behavior.
    MOCK_RATES = {
        "USD": Decimal("1.0"),
        "INR": Decimal("83.0"),
        "EUR": Decimal("0.92"),
        "GBP": Decimal("0.79"),
        "AED": Decimal("3.67"),
        "SGD": Decimal("1.34"),
        "JPY": Decimal("150.0"),
    }

    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Decimal:
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return Decimal("1.0")

        # Convert to USD first, then to target currency
        from_rate = self.MOCK_RATES.get(from_currency)
        to_rate = self.MOCK_RATES.get(to_currency)

        if not from_rate or not to_rate:
            # Fallback to 1.0 if unsupported, though real implementation would raise error
            return Decimal("1.0")

        # from -> USD -> to
        usd_amount = Decimal("1.0") / from_rate
        final_rate = usd_amount * to_rate

        # Return rounded to 6 decimal places for precision
        return final_rate.quantize(Decimal("0.000001"))


def get_currency_rate_provider() -> CurrencyRateProvider:
    """Factory to return the appropriate exchange rate provider."""
    # In a real scenario, this could check settings and return an HTTP API client provider
    return MockCurrencyRateProvider()


def resolve_display_currency(
    user_explicit_currency: str | None = None,
    user_saved_currency: str | None = None,
    client_locale: str | None = None,
    client_country: str | None = None,
) -> str:
    """
    Resolve the currency to display to the user based on priority:
    1. Explicit currency selected by the user
    2. Saved user currency preference
    3. Country/locale provided by the client
    4. Reliable location/country information
    5. Application default currency
    """
    supported_currencies = [
        c.strip().upper() for c in settings.SUPPORTED_CURRENCIES.split(",")
    ]
    default_currency = settings.DEFAULT_CURRENCY.upper()

    def is_supported(curr: str | None) -> bool:
        return bool(curr and curr.upper() in supported_currencies)

    # 1. Explicit currency selected
    if is_supported(user_explicit_currency):
        return user_explicit_currency.upper()  # type: ignore

    # 2. Saved user currency
    if is_supported(user_saved_currency):
        return user_saved_currency.upper()  # type: ignore

    # 3. Client Locale/Country Mapping
    # A robust implementation would use a library or mapping dict like babel
    country_currency_map = {
        "IN": "INR",
        "US": "USD",
        "GB": "GBP",
        "UK": "GBP",
        "AE": "AED",
        "FR": "EUR",
        "DE": "EUR",
        "IT": "EUR",
        "ES": "EUR",
        "JP": "JPY",
        "SG": "SGD",
    }

    if client_country and client_country.upper() in country_currency_map:
        mapped_currency = country_currency_map[client_country.upper()]
        if is_supported(mapped_currency):
            return mapped_currency

    if client_locale:
        # naive locale extraction (e.g. en-US -> US)
        parts = client_locale.replace("_", "-").split("-")
        if len(parts) > 1:
            country_code = parts[-1].upper()
            if country_code in country_currency_map:
                mapped_currency = country_currency_map[country_code]
                if is_supported(mapped_currency):
                    return mapped_currency

    # 4 & 5. Default
    return default_currency
