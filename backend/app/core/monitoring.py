"""
Observability bootstrap for Sentry error reporting and Prometheus metrics.

This module wires up two optional observability integrations at application
startup via :func:`setup_monitoring`:

1. **Sentry** — error tracking and performance tracing.  Activated only
   when ``SENTRY_DSN`` is set in the environment.  ``send_default_pii``
   is forced to ``False`` to comply with GDPR and HACCP data-privacy
   requirements.  A ``before_send`` hook sanitises ``Authorization`` headers
   from breadcrumbs before any event leaves the process boundary.

2. **Prometheus** — HTTP metrics via ``prometheus-fastapi-instrumentator``.
   The ``/metrics`` endpoint is excluded from Starlette's route listing
   (``include_in_schema=False``) and can be protected with a Bearer
   token by setting ``METRICS_TOKEN`` in the environment.
"""

from typing import Any

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


def _sanitize_sentry_event(event: Any, hint: Any) -> Any | None:
    """Strip sensitive headers from Sentry breadcrumbs and request data.

    Removes ``Authorization`` and ``X-Device-Pin`` headers from all
    request contexts embedded in the event to prevent operator credentials
    and PINs from appearing in the Sentry dashboard.

    Expected HTTP exceptions (401, 403, 404) are dropped entirely — they
    represent normal application flow and would create noise in error tracking.

    Args:
        event (dict[str, Any]): The raw Sentry event dict.
        hint (dict[str, Any]): Additional context about the event origin.

    Returns:
        dict[str, Any] | None: The sanitised event, or ``None`` to discard it.
    """
    # Drop expected HTTP errors so they don't pollute the Sentry error count.
    exc_info = hint.get("exc_info")
    if exc_info:
        exc = exc_info[1]
        if hasattr(exc, "status_code") and exc.status_code in (401, 403, 404):
            return None

    # Scrub sensitive request headers wherever they appear.
    _SENSITIVE_HEADERS = frozenset({"authorization", "x-device-pin", "x-platform-admin-key"})
    request_data = event.get("request", {})
    if "headers" in request_data:
        request_data["headers"] = {
            k: "[Filtered]" if k.lower() in _SENSITIVE_HEADERS else v
            for k, v in request_data["headers"].items()
        }

    return event


def setup_monitoring(app: FastAPI) -> None:
    """Initialise Sentry error reporting and Prometheus route metrics.

    Both integrations are gated behind settings flags so they can be
    individually disabled in local or test environments without code changes.

    **Sentry** is initialised with FastAPI, Starlette, and SQLAlchemy
    integrations.  PII transmission is explicitly disabled (``send_default_pii=False``)
    to prevent accidental leakage of operator data to a third-party service.
    The ``release`` field is populated from ``settings.APP_VERSION`` so that
    Sentry can correlate errors to specific deployments.

    **Prometheus** instruments every route except ``/metrics`` itself to
    avoid self-referential noise in the metrics.  When ``METRICS_TOKEN``
    is set, an inner :class:`MetricsAuthMiddleware` is added to gate the
    scrape endpoint with a Bearer token check.

    Args:
        app (FastAPI): The application instance to instrument.
    """
    if settings.SENTRY_DSN:
        sentry_init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=settings.APP_VERSION,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            # Never send PII to Sentry — operator names, emails, and PIN
            # attempts must not leave the application boundary.
            send_default_pii=False,
            before_send=_sanitize_sentry_event,
        )

    if settings.METRICS_ENABLED:
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            excluded_handlers=["/metrics"],
        ).instrument(app).expose(
            app,
            endpoint=settings.METRICS_ENDPOINT,
            include_in_schema=False,
            should_gzip=True,
        )

        if settings.METRICS_TOKEN:
            metrics_path = settings.METRICS_ENDPOINT

            class MetricsAuthMiddleware(BaseHTTPMiddleware):
                """Starlette middleware that protects the Prometheus scrape endpoint.

                Requests to ``METRICS_ENDPOINT`` are rejected with a 401 unless
                the ``Authorization`` header matches ``Bearer <METRICS_TOKEN>``.
                All other paths pass through without inspection.
                """

                async def dispatch(self, request: Request, call_next) -> Response:
                    """Enforce Bearer token authentication on the metrics path.

                    Args:
                        request (Request): The incoming ASGI request.
                        call_next: The next middleware or route handler.

                    Returns:
                        Response: 401 Unauthorized for unauthenticated scrape
                            requests; the original response for all other paths.
                    """
                    if request.url.path == metrics_path:
                        auth = request.headers.get("Authorization", "")
                        if auth != f"Bearer {settings.METRICS_TOKEN}":
                            return Response(status_code=401, content="Unauthorized")
                    return await call_next(request)

            app.add_middleware(MetricsAuthMiddleware)
