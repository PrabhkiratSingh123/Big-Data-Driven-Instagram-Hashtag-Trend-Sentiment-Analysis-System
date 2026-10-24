"""
SocialTrendML — FastAPI Application Entry Point
Main application factory with CORS, routes, startup events, and OpenAPI docs.
"""

import logging
import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.api.routes import (
    health_router,
    hashtag_router,
    collection_router,
    posts_router,
    analytics_router,
    system_router,
)

# Logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("socialtrendml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 SocialTrendML API starting up")
    logger.info(f"   Database: {settings.mongodb_uri}/{settings.mongodb_database}")
    logger.info(f"   API configured: {settings.is_api_configured}")
    if not settings.is_api_configured:
        logger.info("   ⚠️  Running in DEMO MODE (no Instagram API token)")
    logger.info("=" * 60)

    # Initialize database
    from backend.app.database.mongodb import get_db
    try:
        db = get_db()
        logger.info("Database connected and collections initialized")

        # Seed demo data if database is empty and API not configured
        if not settings.is_api_configured:
            post_count = db.get_post_count()
            if post_count == 0:
                logger.info("Seeding demo data for offline exploration...")
                from backend.app.services.demo_data import seed_demo_data
                count = seed_demo_data(db, count=200)
                logger.info(f"Seeded {count} demo posts")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    yield

    # Shutdown
    logger.info("SocialTrendML API shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SocialTrendML API",
        description=(
            "Real-Time Instagram Hashtag Trend & Sentiment Analysis Platform. "
            "Collects Instagram hashtagged posts via the official Graph API, "
            "analyzes sentiment using Spark ML, and provides trend insights."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow dashboard access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://localhost:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(hashtag_router)
    app.include_router(collection_router)
    app.include_router(posts_router)
    app.include_router(analytics_router)
    app.include_router(system_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=True,
    )
