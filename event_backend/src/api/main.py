import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.db import init_db
from src.api.routers.calendar import router as calendar_router
from src.api.routers.events import router as events_router
from src.api.routers.rsvps import router as rsvps_router

logger = logging.getLogger(__name__)

openapi_tags = [
    {"name": "System", "description": "Health checks and service metadata."},
    {"name": "Events", "description": "Create, read, update, delete events (ownership enforced)."},
    {"name": "RSVPs", "description": "Manage RSVPs for events (per-user; owner can list all)."},
    {"name": "Calendar", "description": "Calendar-friendly queries (bucketed by date)."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB schema on startup (best-effort).

    Preview environments may not have a reachable/configured database. We should still
    start the API so `/docs` and health checks load, and only fail DB-backed routes
    when they are called.
    """
    try:
        await init_db()
    except Exception:
        # Intentionally broad: SQLAlchemy/asyncpg may raise a variety of errors when
        # credentials, host/port, or database availability are incorrect.
        logger.warning("Database initialization failed; starting API without DB.", exc_info=True)
    yield


app = FastAPI(
    title="Event Planner API",
    description=(
        "Backend API for Event Planner Pro.\n\n"
        "Auth: Use Supabase JWT in `Authorization: Bearer <token>`.\n"
        "Configure either:\n"
        "- RS256 (recommended): SUPABASE_JWKS_URL, SUPABASE_JWT_AUDIENCE\n"
        "- HS256: SUPABASE_JWT_SECRET, SUPABASE_JWT_AUDIENCE\n"
    ),
    version="0.1.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in cors_origins.split(",")] if cors_origins else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["System"],
    summary="Health check",
    description="Simple health check endpoint.",
    operation_id="health_check",
)
def health_check():
    # PUBLIC_INTERFACE
    """Return a basic health status."""
    return {"message": "Healthy"}


app.include_router(events_router)
app.include_router(rsvps_router)
app.include_router(calendar_router)
