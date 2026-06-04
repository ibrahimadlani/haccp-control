"""
Application-wide runtime configuration via Pydantic Settings.

All configurable values are loaded from environment variables (with optional
``.env`` file fallback for local development).  The ``settings`` singleton at
the bottom of this module is the only place the rest of the application reads
configuration — it is ``lru_cache``-backed to ensure a single parse per process.

Production deployments must override at least:
- ``JWT_SECRET_KEY`` (min 32 chars, must be kept secret)
- ``PLATFORM_ADMIN_KEY`` (min 32 chars, must be kept secret)
- ``DATABASE_URL``
- ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` (real S3 credentials)
Security note:
- ``JWT_SECRET_KEY`` and ``PLATFORM_ADMIN_KEY`` are intentionally required
    (no in-code defaults) to avoid accidental deployment with known secrets.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file.

    Attributes:
        DATABASE_URL (str): Async SQLAlchemy connection string for PostgreSQL.
        JWT_SECRET_KEY (str): HS256 signing secret for all JWT tokens. Minimum
            32 characters; must be rotated if compromised.
        JWT_ALGORITHM (str): JWT signing algorithm. Defaults to ``"HS256"``.
        ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS (int): Lifetime of both
            establishment and organisation JWTs, in hours. Range: 1–24.
        ENVIRONMENT (str): Deployment environment label (``"local"``,
            ``"staging"``, ``"production"``). Used by monitoring integrations.
        SENTRY_DSN (str | None): Sentry error reporting DSN. Disabled when
            ``None``.
        SENTRY_TRACES_SAMPLE_RATE (float): Fraction of transactions sampled for
            Sentry Performance. 0.0 = disabled.
        SENTRY_PROFILES_SAMPLE_RATE (float): Fraction of sampled transactions
            profiled by Sentry. 0.0 = disabled.
        METRICS_ENABLED (bool): Whether to expose the Prometheus ``/metrics``
            endpoint.
        METRICS_ENDPOINT (str): URL path for the Prometheus scrape endpoint.
        METRICS_TOKEN (str | None): Optional Bearer token protecting
            ``/metrics``. When ``None``, the endpoint is unrestricted.
        PLATFORM_ADMIN_KEY (str): API key required for irreversible platform
            operations (tenant creation, hard deletes). Minimum 32 characters.
        AWS_ACCESS_KEY_ID (str): AWS or MinIO access key for S3 uploads.
        AWS_SECRET_ACCESS_KEY (str): AWS or MinIO secret key.
        AWS_REGION (str): AWS region or MinIO region label.
        AWS_ENDPOINT_URL (str): S3-compatible endpoint URL. Defaults to the
            local MinIO instance.
        S3_PUBLIC_ENDPOINT_URL (str): Base URL used to build public object URLs
            for client download links.
        S3_BUCKET_NAME (str): Target S3 bucket for all uploads (photos, BL).
        BACKEND_CORS_ORIGINS (list[str]): Allowed browser origins for CORS.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    _INSECURE_SECRET_MARKERS = (
        "change-me",
        "changeme",
        "default",
        "example",
        "placeholder",
        "secret",
        "minioadmin",
    )

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://haccp_user:haccp_password@db:5432/haccp_control",
        description="Async SQLAlchemy PostgreSQL database URL.",
    )
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Secret used to sign JWT tokens in future authentication flows.",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=12, ge=1, le=24)
    ENVIRONMENT: str = Field(default="local")
    APP_VERSION: str = Field(
        default="0.0.0-local",
        description="Application version tag embedded in Sentry releases.",
    )
    SENTRY_DSN: str | None = Field(default=None)
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.0, ge=0.0, le=1.0)
    SENTRY_PROFILES_SAMPLE_RATE: float = Field(default=0.0, ge=0.0, le=1.0)
    METRICS_ENABLED: bool = Field(default=True)
    METRICS_ENDPOINT: str = Field(default="/metrics")
    METRICS_TOKEN: str | None = Field(
        default=None,
        description="Bearer token to protect /metrics endpoint. If None, metrics are unrestricted.",
    )
    PLATFORM_ADMIN_KEY: str = Field(
        ...,
        min_length=32,
        description="Secret key for platform-level admin endpoints (e.g. tenant creation).",
    )
    AWS_ACCESS_KEY_ID: str = Field(default="minioadmin")
    AWS_SECRET_ACCESS_KEY: str = Field(default="minioadmin")
    AWS_REGION: str = Field(default="eu-west-3")
    AWS_ENDPOINT_URL: str = Field(default="http://minio:9000")
    S3_PUBLIC_ENDPOINT_URL: str = Field(default="http://localhost:9000")
    S3_BUCKET_NAME: str = Field(default="haccp-documents")
    BACKEND_CORS_ORIGINS: Annotated[
        list[str],
        Field(
            default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
            description="Allowed origins for browser clients.",
        ),
    ]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Reject weak/default credentials in staging and production environments."""
        environment = self.ENVIRONMENT.lower().strip()
        if environment not in {"staging", "production"}:
            return self

        secret_fields = {
            "JWT_SECRET_KEY": self.JWT_SECRET_KEY,
            "PLATFORM_ADMIN_KEY": self.PLATFORM_ADMIN_KEY,
        }
        for field_name, value in secret_fields.items():
            lowered = value.lower()
            if any(marker in lowered for marker in self._INSECURE_SECRET_MARKERS):
                raise ValueError(
                    f"{field_name} is insecure for {environment}. Use a strong random secret."
                )

        if self.AWS_ACCESS_KEY_ID == "minioadmin" or self.AWS_SECRET_ACCESS_KEY == "minioadmin":
            raise ValueError(
                f"AWS credentials are insecure for {environment}. Use real non-default credentials."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    The ``lru_cache`` decorator ensures that environment variables and the
    ``.env`` file are parsed exactly once per process lifetime, regardless of
    how many times ``get_settings()`` is called across the codebase.

    Returns:
        Settings: The fully validated settings instance.
    """
    return Settings()


# Module-level singleton — import ``settings`` directly instead of calling
# ``get_settings()`` at every use site.
settings = get_settings()
