"""
Application configuration, loaded from environment variables / .env.

Every client deployment should only need to change the .env file —
never this code — to point at a different database or adjust settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Vertex Base API"
    environment: str = "development"  # development | staging | production
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vertex_base"

    # CORS — set to your actual frontend origin(s) in production
    cors_origins: list[str] = ["http://localhost:5173"]

    # Auth (placeholder — swap for real secret management per client)
    secret_key: str = "change-me-in-every-real-deployment"
    access_token_expire_minutes: int = 60 * 24  # 24h


settings = Settings()
