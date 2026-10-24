"""
SocialTrendML — API Routes
All FastAPI endpoint handlers organized by domain.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from backend.app.database.mongodb import get_db
from backend.app.services.analytics import AnalyticsService
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

# =====================================================================
# Routers
# =====================================================================

health_router = APIRouter(tags=["Health"])
hashtag_router = APIRouter(prefix="/api/hashtags", tags=["Hashtags"])
collection_router = APIRouter(prefix="/api/collection", tags=["Collection"])
posts_router = APIRouter(prefix="/api/posts", tags=["Posts"])
analytics_router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
system_router = APIRouter(prefix="/api/system", tags=["System"])

_start_time = time.time()


def _get_service() -> AnalyticsService:
    return AnalyticsService()


# =====================================================================
# Health
# =====================================================================

@health_router.get("/health")
def health_check():
    """Basic health check endpoint."""
    db = get_db()
    db_ok = db.is_connected()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


# =====================================================================
# Hashtags
# =====================================================================

class TrackHashtagRequest(BaseModel):
    hashtag: str = Field(..., min_length=1, max_length=100, description="Hashtag to track (without #)")


@hashtag_router.get("/search")
def search_hashtag(q: str = Query(..., min_length=1, max_length=100, description="Hashtag to search")):
    """
    Search for a hashtag on Instagram.
    Returns the hashtag ID if the API is configured, otherwise indicates demo mode.
    """
    settings = get_settings()
    service = _get_service()

    if not service.collector.is_configured:
        return {
            "hashtag": q.strip().lower().lstrip("#"),
            "found": True,
            "demo_mode": True,
            "message": "API not configured. Results will use demo data.",
        }

    try:
        hashtag_id = service.collector.search_hashtag(q)
        return {
            "hashtag": q.strip().lower().lstrip("#"),
            "hashtag_id": hashtag_id,
            "found": hashtag_id is not None,
            "demo_mode": False,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Instagram API error: {str(e)}")


@hashtag_router.post("/track")
def track_hashtag(request: TrackHashtagRequest, background_tasks: BackgroundTasks):
    """
    Start tracking a hashtag. Triggers an immediate collection run in the background.
    """
    hashtag = request.hashtag.strip().lower().lstrip("#")
    service = _get_service()

    # Run collection in background
    background_tasks.add_task(service.run_collection, [hashtag])

    return {
        "hashtag": hashtag,
        "status": "tracking_started",
        "message": f"Collection for #{hashtag} started in background.",
        "demo_mode": not service.collector.is_configured,
    }


@hashtag_router.get("")
def get_tracked_hashtags():
    """Get all currently tracked hashtags with post counts."""
    db = get_db()
    hashtags = db.get_unique_hashtags()
    result = []
    for h in hashtags:
        count = db.get_post_count(hashtag=h)
        result.append({"hashtag": h, "post_count": count})
    return {"hashtags": sorted(result, key=lambda x: x["post_count"], reverse=True)}


# =====================================================================
# Collection
# =====================================================================

class RunCollectionRequest(BaseModel):
    hashtags: list[str] = Field(default_factory=list, description="Hashtags to collect. If empty, uses defaults.")


@collection_router.post("/run")
def run_collection(request: RunCollectionRequest, background_tasks: BackgroundTasks):
    """
    Trigger a data collection run.
    Collects posts for specified hashtags (or defaults), runs sentiment analysis,
    and updates metrics.
    """
    service = _get_service()
    hashtags = [h.strip().lower().lstrip("#") for h in request.hashtags if h.strip()] or None

    # Run in background for long-running collection
    background_tasks.add_task(service.run_collection, hashtags)

    return {
        "status": "collection_started",
        "hashtags": hashtags or service.settings.default_hashtags_list,
        "demo_mode": not service.collector.is_configured,
        "message": "Collection started in background. Check /api/system/status for progress.",
    }


# =====================================================================
# Posts
# =====================================================================

@posts_router.get("")
def get_posts(
    hashtag: Optional[str] = Query(None, description="Filter by source hashtag"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Get collected posts with optional hashtag filter and pagination."""
    db = get_db()
    posts = db.get_posts(hashtag=hashtag, limit=limit, skip=skip)
    total = db.get_post_count(hashtag=hashtag)

    # Sanitize output — never expose internal fields
    clean_posts = []
    for p in posts:
        clean_posts.append({
            "post_id": p.get("post_id"),
            "caption": p.get("caption", ""),
            "media_type": p.get("media_type", "IMAGE"),
            "permalink": p.get("permalink", ""),
            "timestamp": p.get("timestamp"),
            "hashtags": p.get("hashtags", []),
            "source_hashtag": p.get("source_hashtag", ""),
            "is_demo": p.get("is_demo", False),
        })

    return {"posts": clean_posts, "total": total, "limit": limit, "skip": skip}


# =====================================================================
# Analytics
# =====================================================================

@analytics_router.get("/overview")
def get_overview():
    """Get dashboard overview with key metrics and distributions."""
    service = _get_service()
    return service.get_overview()


@analytics_router.get("/trends")
def get_trends(limit: int = Query(20, ge=1, le=100)):
    """Get trending hashtags ranked by trend score."""
    service = _get_service()
    trends = service.get_trends(limit=limit)
    return {"trends": trends}


@analytics_router.get("/sentiment")
def get_sentiment(hashtag: Optional[str] = Query(None)):
    """Get sentiment analysis overview with distributions and top keywords."""
    service = _get_service()
    return service.get_sentiment_overview(hashtag=hashtag)


@analytics_router.get("/hashtag/{hashtag}/activity")
def get_hashtag_activity(hashtag: str, days: int = Query(7, ge=1, le=90)):
    """Get daily activity for a specific hashtag."""
    db = get_db()
    daily = db.get_hashtag_activity(hashtag, days=days)
    hourly = db.get_hourly_activity(hashtag, days=days)
    return {
        "hashtag": hashtag,
        "daily_activity": [{"date": d["_id"], "count": d["count"]} for d in daily],
        "hourly_distribution": [{"hour": h["_id"], "count": h["count"]} for h in hourly],
    }


@analytics_router.get("/engagement")
def get_engagement(limit: int = Query(20, ge=1, le=100)):
    """Get engagement leaderboard, platform summary, and scatter points."""
    service = _get_service()
    return service.get_engagement_overview(limit=limit)


# =====================================================================
# System
# =====================================================================

@system_router.get("/status")
def get_system_status():
    """Get overall system status including database, API, and processing state."""
    settings = get_settings()
    db = get_db()

    # Database status
    db_status = "connected" if db.is_connected() else "disconnected"

    # API status
    if settings.meta_access_token:
        api_status = "configured"
    else:
        api_status = "unconfigured (demo mode)"

    # Kafka status
    kafka_status = "unknown"
    try:
        from kafka import KafkaProducer as KP
        kp = KP(bootstrap_servers=settings.kafka_bootstrap_servers, request_timeout_ms=3000)
        kp.close()
        kafka_status = "connected"
    except Exception:
        kafka_status = "disconnected"

    # Collection info
    last_run = db.get_latest_collection_run()
    errors = db.get_recent_errors(limit=5)

    return {
        "api_status": api_status,
        "database_status": db_status,
        "kafka_status": kafka_status,
        "total_posts": db.get_post_count(),
        "tracked_hashtags": len(db.get_unique_hashtags()),
        "last_collection": last_run,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "recent_errors": errors,
    }
