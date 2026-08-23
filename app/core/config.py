from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Itvaya Travel API"
    APP_ENV: str = "development"
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS / Frontend
    CORS_ALLOWED_ORIGINS: str = ""

    # Clerk Authentication
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWT_KEY: str = ""

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

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.APP_ENV == "production":
            missing = []
            if not self.DATABASE_URL:
                missing.append("DATABASE_URL")
            if not self.SECRET_KEY:
                missing.append("SECRET_KEY")
            if not self.CORS_ALLOWED_ORIGINS:
                missing.append("CORS_ALLOWED_ORIGINS")
            # Ensure Clerk configuration is set
            if not self.CLERK_SECRET_KEY:
                missing.append("CLERK_SECRET_KEY")
            if not self.CLERK_PUBLISHABLE_KEY:
                missing.append("CLERK_PUBLISHABLE_KEY")
            
            # Payment provider specific
            if self.PAYMENT_PROVIDER == "stripe":
                if not self.STRIPE_SECRET_KEY:
                    missing.append("STRIPE_SECRET_KEY")
                if not self.STRIPE_WEBHOOK_SECRET:
                    missing.append("STRIPE_WEBHOOK_SECRET")

            if missing:
                raise ValueError(
                    f"Missing required production configuration variables: {', '.join(missing)}"
                )
        elif self.APP_ENV == "development":
            # Provide development fallback for critical local execution if not in .env
            if not self.DATABASE_URL:
                self.DATABASE_URL = "postgresql+asyncpg://user:password@localhost/itvaya"
            if not self.SECRET_KEY:
                self.SECRET_KEY = "change_this_in_production_environment_with_strong_secret"
                
        return self


settings = Settings()
