"""
FastAPI application entry point for the HACCP Control SaaS platform.

This module bootstraps the ASGI application, registers all domain-level routers,
configures CORS, and attaches the Prometheus observability middleware.
"""

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text

from app.api.deps import DatabaseSession
from app.api.router import api_router as rest_v1_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.monitoring import setup_monitoring

# Configure structured logging before anything else so that all startup
# messages (including SQLAlchemy engine init) flow through the pipeline.
configure_logging(settings.ENVIRONMENT)

logger = structlog.get_logger(__name__)


app = FastAPI(
    title="HACCP Control API",
    description="REST API for HACCP sanitary traceability workflows.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_monitoring(app)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Bind a unique request_id and request metadata to the structlog context.

    Every log event emitted during this request automatically carries
    ``request_id``, ``method``, and ``path`` without any explicit passing.
    The context is cleared after the response is sent to prevent leaking
    state across requests in the same worker thread.

    Args:
        request (Request): The incoming ASGI request object.
        call_next: The next ASGI middleware or route handler in the chain.

    Returns:
        Response: The unmodified response from downstream handlers.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid.uuid4()),
        method=request.method,
        path=request.url.path,
    )
    response: Response = await call_next(request)
    return response


app.include_router(rest_v1_router)


@app.get("/health", tags=["System"])
async def health_check(db: DatabaseSession) -> dict[str, Any]:
    """Verify that the API process and the PostgreSQL database are reachable.

    Intended for use by load-balancers, container orchestrators (e.g. Kubernetes
    liveness/readiness probes), and monitoring systems.

    Args:
        db (DatabaseSession): An injected async database session used to run a
            lightweight connectivity probe query.

    Returns:
        dict[str, Any]: A JSON body ``{"status": "ok", "database": "ok"}`` when
            both the API and the database are healthy.

    Raises:
        HTTPException: 503 Service Unavailable if the database probe query fails,
            carrying ``{"status": "error", "database": "unavailable"}`` in the
            detail payload.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "unavailable"},
        ) from exc

    return {"status": "ok", "database": "ok"}
