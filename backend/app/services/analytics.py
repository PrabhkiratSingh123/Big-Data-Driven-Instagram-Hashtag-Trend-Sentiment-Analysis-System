"""
SocialTrendML — Analytics Service
Orchestrates data collection, sentiment analysis, and metric computation.
"""

import logging
from datetime import datetime, timezone
from collections import Counter
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.database.mongodb import MongoDBManager, get_db
from backend.app.collectors.instagram import InstagramCollector
from backend.app.ml.sentiment import (
    get_sentiment_analyzer,
    extract_keywords,
    extract_hashtags_from_caption,
    calculate_trend_score,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Main orchestration service for SocialTrendML.
    Coordinates collection, analysis, and metric computation.
    """

    def __init__(self, db: Optional[MongoDBManager] = None):
        self.settings = get_settings()
        self.db = db or get_db()
        self.collector = InstagramCollector()
        self._analyzer = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            self._analyzer = get_sentiment_analyzer()
        return self._analyzer

    def run_collection(self, hashtags: Optional[list[str]] = None) -> dict:
        """
        Execute a full collection + analysis cycle:
        1. Collect posts from Instagram API (or demo data)
        2. Store in MongoDB
        3. Run sentiment analysis
        4. Update hashtag metrics
        5. Record collection run

        Returns:
            Summary dict with counts and status.
        """
        if hashtags is None:
            hashtags = self.settings.default_hashtags_list

        is_demo = not self.collector.is_configured
        run_id = self.db.create_collection_run(hashtags, is_demo=is_demo)

        try:
            if self.collector.is_configured:
                # Real Instagram API collection
                logger.info(f"Collecting from Instagram API for hashtags: {hashtags}")
                posts = self.collector.collect_multiple_hashtags(hashtags)
            else:
                # Demo mode
                logger.info(f"API not configured — generating demo data for: {hashtags}")
                from backend.app.services.demo_data import generate_demo_batch
                posts = generate_demo_batch(count=len(hashtags) * 15, hashtags=hashtags)

            if not posts:
                self.db.complete_collection_run(run_id, 0, "completed", "No posts returned")
                return {"run_id": run_id, "status": "completed", "posts_collected": 0, "is_demo": is_demo}

            # Store posts
            stored = self.db.upsert_posts(posts)

            # Sentiment analysis
            sentiments = self._analyze_sentiments(posts)

            # Update hashtag metrics
            self._update_hashtag_metrics(hashtags)

            self.db.complete_collection_run(run_id, stored)
            logger.info(f"Collection run {run_id} complete: {stored} posts stored, {len(sentiments)} analyzed")

            return {
                "run_id": run_id,
                "status": "completed",
                "posts_collected": stored,
                "sentiments_analyzed": len(sentiments),
                "is_demo": is_demo,
                "hashtags": hashtags,
            }

        except Exception as e:
            error_msg = str(e)
            # Sanitize — never include token in error messages
            if self.settings.meta_access_token and self.settings.meta_access_token in error_msg:
                error_msg = error_msg.replace(self.settings.meta_access_token, "[REDACTED]")

            logger.error(f"Collection run {run_id} failed: {error_msg}")
            self.db.complete_collection_run(run_id, 0, "failed", error_msg)
            return {"run_id": run_id, "status": "failed", "error": error_msg, "is_demo": is_demo}

    def _analyze_sentiments(self, posts: list[dict]) -> list[dict]:
        """Run sentiment analysis on posts and store results."""
        try:
            results = self.analyzer.analyze_batch(posts)
            if results:
                self.db.upsert_sentiment_results(results)
            return results
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return []

    def _update_hashtag_metrics(self, hashtags: list[str]):
        """Recompute and update hashtag metrics."""
        try:
            metrics = []
            for hashtag in hashtags:
                posts = self.db.get_posts(hashtag=hashtag, limit=1000)
                if not posts:
                    continue

                # Get sentiment distribution for this hashtag
                sentiment_dist = self.db.get_sentiment_distribution(hashtag=hashtag)
                total_sentiments = sum(sentiment_dist.values()) or 1

                # Keyword aggregation
                all_keywords = []
                for p in posts:
                    all_keywords.extend(extract_keywords(p.get("caption", "")))
                top_kw = [w for w, _ in Counter(all_keywords).most_common(10)]

                # Calculate trend score
                recent = len([p for p in posts if p.get("timestamp") and
                             (datetime.now(timezone.utc) - p["timestamp"]).total_seconds() < 86400])
                older = len(posts) - recent

                avg_sent = (sentiment_dist.get("positive", 0) - sentiment_dist.get("negative", 0)) / total_sentiments

                total_likes = sum(p.get("likes_count", 0) for p in posts)
                total_comments = sum(p.get("comments_count", 0) for p in posts)
                n_posts = max(len(posts), 1)

                metrics.append({
                    "hashtag": hashtag,
                    "post_count": len(posts),
                    "avg_sentiment": avg_sent,
                    "positive_ratio": sentiment_dist.get("positive", 0) / total_sentiments,
                    "negative_ratio": sentiment_dist.get("negative", 0) / total_sentiments,
                    "neutral_ratio": sentiment_dist.get("neutral", 0) / total_sentiments,
                    "top_keywords": top_kw,
                    "trend_score": calculate_trend_score(recent, older, avg_sent),
                    "avg_likes": round(total_likes / n_posts, 1),
                    "avg_comments": round(total_comments / n_posts, 1),
                    "engagement_rate": round((total_likes + total_comments) / n_posts, 2),
                    "period_start": min((p["timestamp"] for p in posts if p.get("timestamp")), default=datetime.now(timezone.utc)),
                    "period_end": max((p["timestamp"] for p in posts if p.get("timestamp")), default=datetime.now(timezone.utc)),
                })

            if metrics:
                self.db.upsert_hashtag_metrics(metrics)

        except Exception as e:
            logger.error(f"Failed to update hashtag metrics: {e}")

    def get_overview(self) -> dict:
        """Get dashboard overview data."""
        total_posts = self.db.get_post_count()
        hashtags = self.db.get_unique_hashtags()
        sentiment_dist = self.db.get_sentiment_distribution()
        last_run = self.db.get_latest_collection_run()
        engagement = self.db.get_engagement_summary()

        return {
            "total_posts": total_posts,
            "tracked_hashtags": len(hashtags),
            "sentiment_distribution": sentiment_dist,
            "recent_hashtags": hashtags[:10],
            "last_collection": last_run,
            "engagement_summary": engagement,
            "api_configured": self.collector.is_configured,
            "demo_mode": not self.collector.is_configured,
        }

    def get_trends(self, limit: int = 20) -> list[dict]:
        """Get trending hashtags with metrics."""
        return self.db.get_trending_hashtags(limit=limit)

    def get_sentiment_overview(self, hashtag: Optional[str] = None) -> dict:
        """Get sentiment analysis overview."""
        distribution = self.db.get_sentiment_distribution(hashtag=hashtag)
        over_time = self.db.get_sentiment_over_time(days=7, hashtag=hashtag)
        pos_keywords = self.db.get_top_keywords(sentiment="positive", limit=15)
        neg_keywords = self.db.get_top_keywords(sentiment="negative", limit=15)

        return {
            "distribution": distribution,
            "over_time": over_time,
            "positive_keywords": [{"keyword": k["_id"], "count": k["count"]} for k in pos_keywords],
            "negative_keywords": [{"keyword": k["_id"], "count": k["count"]} for k in neg_keywords],
        }

    def get_engagement_overview(self, limit: int = 20) -> dict:
        """Get engagement metrics overview."""
        leaderboard = self.db.get_engagement_leaderboard(limit=limit)
        summary = self.db.get_engagement_summary()
        scatter_points = self.db.get_likes_vs_comments(limit=100)
        return {
            "summary": summary,
            "leaderboard": leaderboard,
            "scatter_points": scatter_points,
        }
