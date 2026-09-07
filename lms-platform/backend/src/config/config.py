"""Validated environment settings; importing this module does not load secrets."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "LMS API"
    database_url: SecretStr
    # Docker Desktop connects to Windows MySQL through host.docker.internal.
    db_host_override: str | None = None
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "lms-api"
    jwt_audience: str = "lms-client"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_recycle: int = Field(default=1800, ge=1)
    db_pool_timeout: int = Field(default=30, ge=1)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "mysql+aiomysql"
                and url.host
                and url.username
                and url.database
                and url.query.get("charset", "utf8mb4") == "utf8mb4"
            )
        except Exception:
            valid = False
        if not valid:
            raise ValueError("Use mysql+aiomysql with host, username, database and utf8mb4")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def reject_placeholder(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().lower().startswith(("replace-", "change", "example")):
            raise ValueError("Generate a random JWT secret before starting the application")
        return value

    @property
    def sqlalchemy_url(self) -> URL:
        """Keep credentials out of repr/logging and force utf8mb4 on every connection."""
        url = make_url(self.database_url.get_secret_value())
        if self.db_host_override:
            url = url.set(host=self.db_host_override)
        return url.update_query_dict({"charset": "utf8mb4"})


@lru_cache
def get_settings() -> Settings:
    return Settings()
