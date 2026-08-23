from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Itvaya Travel API"
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/itvaya"
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "change_this_in_production_environment_with_strong_secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Clerk Authentication
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""

    # Payment provider: "razorpay" or "mock"
    PAYMENT_PROVIDER: str = "mock"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Platform financials
    PLATFORM_COMMISSION_RATE: float = 0.15  # 15%
    # Stripe configurations
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Currency & Exchange
    DEFAULT_CURRENCY: str = "INR"
    SUPPORTED_CURRENCIES: str = "INR,USD,EUR,GBP,AED,SGD,JPY"
    CURRENCY_API_URL: str = ""
    CURRENCY_API_KEY: str = ""

    # Retry configurations
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_INITIAL_DELAY_SECONDS: float = 1.0
    RETRY_MAX_DELAY_SECONDS: float = 10.0
    RETRY_BACKOFF_MULTIPLIER: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
