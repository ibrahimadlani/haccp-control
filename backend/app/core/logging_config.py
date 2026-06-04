"""
Structured logging configuration using structlog.

Provides :func:`configure_logging` which must be called once at application
startup (in ``app/main.py``).  The output format adapts to the environment:

- **local / test**: colourised, human-readable ``ConsoleRenderer``
- **staging / production**: JSON (``JSONRenderer``), one log line per event,
  directly parseable by Grafana Loki / Promtail.

All log entries produced by ``structlog.get_logger()`` automatically carry
the context variables bound via :func:`structlog.contextvars.bind_contextvars`,
which the request-context middleware populates per HTTP request (``request_id``,
``method``, ``path``).
"""

import logging
import sys

import structlog


def configure_logging(environment: str) -> None:
    """Configure structlog for the given deployment environment.

    Must be called once before the ASGI application starts serving requests.
    Calling it multiple times is safe (structlog reconfigures in-place), but
    should be avoided in production.

    Args:
        environment (str): The deployment environment, e.g. ``"local"``,
            ``"staging"``, or ``"production"``.  Any value other than
            ``"production"`` or ``"staging"`` uses the developer-friendly
            console renderer.
    """
    shared_processors: list[structlog.types.Processor] = [
        # Merge request-scoped context vars (request_id, path, method) into
        # every log event emitted during that request, without explicit passing.
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        # add_logger_name is intentionally omitted: it requires a stdlib Logger
        # object with a .name attribute, which PrintLoggerFactory does not provide.
        # The module name is already embedded by passing __name__ to get_logger().
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if environment in ("production", "staging"):
        # JSON output: one object per line, parseable by Promtail/Loki.
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Colourised multi-line output for local development.
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Redirect stdlib logging (SQLAlchemy, uvicorn, etc.) through structlog so
    # that all log output flows through the same pipeline and ends up in Loki.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    for noisy_logger in ("uvicorn.access",):
        # uvicorn.access logs every request at INFO — too verbose; set to WARNING.
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
