from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Itvaya Travel API"
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/itvaya"
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "change_this_in_production"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
