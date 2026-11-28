from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: PostgresDsn
    cors_origins: str = ""

    @field_validator("database_url")
    @classmethod
    def require_psycopg(cls, url: PostgresDsn) -> PostgresDsn:
        if url.scheme != "postgresql+psycopg" or not url.path or url.path == "/":
            raise ValueError("Use a postgresql+psycopg URL with a database name")
        return url
