"""
SocialTrendML — Pydantic Models
Data models for API requests, responses, and internal data structures.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# =====================================================================
# Instagram Data Models
# =====================================================================

class InstagramPost(BaseModel):
    """Represents an Instagram post from the Graph API."""
    post_id: str = Field(..., description="Instagram media ID")
    caption: str = Field(default="", description="Post caption text")
    media_type: str = Field(default="IMAGE", description="IMAGE, VIDEO, or CAROUSEL_ALBUM")
    permalink: str = Field(default="", description="Link to the original post")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    hashtags: list[str] = Field(default_factory=list)
    source_hashtag: str = Field(default="", description="The hashtag query that found this post")
    likes_count: int = Field(default=0, description="Number of likes")
    comments_count: int = Field(default=0, description="Number of comments")
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    is_demo: bool = Field(default=False, description="True if this is synthetic demo data")


class SentimentResult(BaseModel):
    """Sentiment analysis result for a post."""
    post_id: str
    caption: str = ""
    sentiment: str = Field(..., description="positive, negative, or neutral")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class HashtagMetric(BaseModel):
    """Aggregated metrics for a hashtag."""
    hashtag: str
    post_count: int = 0
    avg_sentiment: float = 0.0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    neutral_ratio: float = 0.0
    top_keywords: list[str] = Field(default_factory=list)
    trend_score: float = 0.0
    period_start: datetime = Field(default_factory=datetime.utcnow)
    period_end: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CollectionRun(BaseModel):
    """Record of a data collection run."""
    run_id: str = ""
    hashtags: list[str] = Field(default_factory=list)
    posts_collected: int = 0
    status: str = "pending"
    error_message: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    is_demo: bool = False


# =====================================================================
# API Request/Response Models
# =====================================================================

class HashtagSearchRequest(BaseModel):
    """Request to search a hashtag on Instagram."""
    q: str = Field(..., min_length=1, max_length=100, description="Hashtag to search (without #)")


class HashtagTrackRequest(BaseModel):
    """Request to start tracking a hashtag."""
    hashtag: str = Field(..., min_length=1, max_length=100)


class CollectionRunRequest(BaseModel):
    """Request to trigger a collection run."""
    hashtags: list[str] = Field(default_factory=list, description="Hashtags to collect. If empty, uses defaults.")


class OverviewResponse(BaseModel):
    """Dashboard overview metrics."""
    total_posts: int = 0
    tracked_hashtags: int = 0
    sentiment_distribution: dict = Field(default_factory=dict)
    recent_hashtags: list[str] = Field(default_factory=list)
    last_collection: Optional[dict] = None
    api_configured: bool = False
    demo_mode: bool = True


class TrendResponse(BaseModel):
    """Trend analytics data."""
    hashtag: str
    post_count: int = 0
    trend_score: float = 0.0
    sentiment_avg: float = 0.0
    daily_counts: list[dict] = Field(default_factory=list)


class SystemStatusResponse(BaseModel):
    """System health and status."""
    api_status: str = "unconfigured"
    database_status: str = "disconnected"
    kafka_status: str = "unknown"
    last_collection: Optional[str] = None
    total_posts: int = 0
    uptime: str = ""
    errors: list[str] = Field(default_factory=list)
