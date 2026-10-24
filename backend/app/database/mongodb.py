"""
SocialTrendML — MongoDB Database Layer
Handles all MongoDB operations: connection management, CRUD operations,
indexing, and aggregation queries for the analytics platform.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from pymongo import MongoClient, UpdateOne, DESCENDING, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import (
    ConnectionFailure,
    BulkWriteError,
    DuplicateKeyError,
    PyMongoError,
)

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class MongoDBManager:
    """
    MongoDB manager with connection pooling, collection management,
    and all data operations for SocialTrendML.
    """

    COLLECTIONS = [
        "instagram_posts",
        "hashtag_metrics",
        "sentiment_results",
        "collection_runs",
    ]

    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None):
        settings = get_settings()
        self.uri = uri or settings.mongodb_uri
        self.database_name = database or settings.mongodb_database
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

    def connect(self) -> Database:
        """Establish MongoDB connection with pooling."""
        if self._client is None:
            try:
                self._client = MongoClient(
                    self.uri,
                    maxPoolSize=50,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    retryWrites=True,
                )
                self._client.admin.command("ping")
                self._db = self._client[self.database_name]
                logger.info(f"Connected to MongoDB: {self.database_name}")
            except ConnectionFailure as e:
                logger.error(f"MongoDB connection failed: {e}")
                raise
        return self._db

    @property
    def db(self) -> Database:
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, name: str) -> Collection:
        return self.db[name]

    def is_connected(self) -> bool:
        """Check if MongoDB is reachable."""
        try:
            if self._client:
                self._client.admin.command("ping")
                return True
            return False
        except Exception:
            return False

    # -----------------------------------------------------------------
    # Setup & Indexes
    # -----------------------------------------------------------------

    def setup_collections(self):
        """Create collections and indexes."""
        existing = self.db.list_collection_names()
        for coll in self.COLLECTIONS:
            if coll not in existing:
                self.db.create_collection(coll)
                logger.info(f"Created collection: {coll}")

        # instagram_posts indexes
        posts = self.get_collection("instagram_posts")
        posts.create_index("post_id", unique=True, name="idx_post_id")
        posts.create_index([("timestamp", DESCENDING)], name="idx_timestamp")
        posts.create_index("source_hashtag", name="idx_source_hashtag")
        posts.create_index(
            [("source_hashtag", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_hashtag_time",
        )
        posts.create_index([("collected_at", DESCENDING)], name="idx_collected_at")

        # hashtag_metrics indexes
        metrics = self.get_collection("hashtag_metrics")
        metrics.create_index(
            [("hashtag", ASCENDING), ("period_start", DESCENDING)],
            unique=True,
            name="idx_hashtag_period",
        )
        metrics.create_index([("trend_score", DESCENDING)], name="idx_trend_score")
        metrics.create_index([("updated_at", DESCENDING)], name="idx_updated")

        # sentiment_results indexes
        sentiment = self.get_collection("sentiment_results")
        sentiment.create_index("post_id", unique=True, name="idx_post_id")
        sentiment.create_index(
            [("sentiment", ASCENDING), ("analyzed_at", DESCENDING)],
            name="idx_sentiment_time",
        )
        sentiment.create_index([("analyzed_at", DESCENDING)], name="idx_analyzed")

        # collection_runs indexes
        runs = self.get_collection("collection_runs")
        runs.create_index("run_id", unique=True, name="idx_run_id")
        runs.create_index([("started_at", DESCENDING)], name="idx_started")

        logger.info("All indexes created successfully")

    # -----------------------------------------------------------------
    # Instagram Posts
    # -----------------------------------------------------------------

    def upsert_posts(self, posts: list[dict]) -> int:
        """Upsert posts using post_id as the unique key. Returns count of modified/inserted."""
        if not posts:
            return 0

        collection = self.get_collection("instagram_posts")
        operations = []

        for post in posts:
            # Normalize timestamp
            if isinstance(post.get("timestamp"), str):
                try:
                    post["timestamp"] = datetime.fromisoformat(
                        post["timestamp"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    post["timestamp"] = datetime.now(timezone.utc)

            post.setdefault("collected_at", datetime.now(timezone.utc))

            operations.append(
                UpdateOne(
                    {"post_id": post["post_id"]},
                    {"$set": post, "$setOnInsert": {"first_seen": datetime.now(timezone.utc)}},
                    upsert=True,
                )
            )

        try:
            result = collection.bulk_write(operations, ordered=False)
            total = result.upserted_count + result.modified_count
            logger.info(f"Upserted {total} posts ({result.upserted_count} new, {result.modified_count} updated)")
            return total
        except BulkWriteError as e:
            inserted = e.details.get("nInserted", 0) + e.details.get("nUpserted", 0)
            logger.warning(f"Bulk write partial: {inserted} processed, {len(e.details.get('writeErrors', []))} errors")
            return inserted

    def get_posts(
        self,
        hashtag: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Query posts with optional filters."""
        collection = self.get_collection("instagram_posts")
        query: dict[str, Any] = {}

        if hashtag:
            query["source_hashtag"] = hashtag
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date

        return list(
            collection.find(query, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

    def get_post_count(self, hashtag: Optional[str] = None) -> int:
        collection = self.get_collection("instagram_posts")
        query = {"source_hashtag": hashtag} if hashtag else {}
        return collection.count_documents(query)

    def get_unique_hashtags(self) -> list[str]:
        """Get all unique source hashtags."""
        collection = self.get_collection("instagram_posts")
        return collection.distinct("source_hashtag")

    # -----------------------------------------------------------------
    # Sentiment Results
    # -----------------------------------------------------------------

    def upsert_sentiment_results(self, results: list[dict]) -> int:
        """Upsert sentiment analysis results."""
        if not results:
            return 0

        collection = self.get_collection("sentiment_results")
        operations = []

        for result in results:
            result.setdefault("analyzed_at", datetime.now(timezone.utc))
            operations.append(
                UpdateOne(
                    {"post_id": result["post_id"]},
                    {"$set": result},
                    upsert=True,
                )
            )

        try:
            res = collection.bulk_write(operations, ordered=False)
            total = res.upserted_count + res.modified_count
            logger.info(f"Upserted {total} sentiment results")
            return total
        except BulkWriteError as e:
            logger.warning(f"Sentiment bulk write error: {e.details}")
            return 0

    def get_sentiment_distribution(self, hashtag: Optional[str] = None) -> dict:
        """Get sentiment distribution counts."""
        collection = self.get_collection("sentiment_results")
        match_stage = {}
        if hashtag:
            match_stage = {"$match": {"source_hashtag": hashtag}}

        pipeline = []
        if match_stage:
            pipeline.append(match_stage)
        pipeline.extend([
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
            {"$sort": {"count": DESCENDING}},
        ])

        results = list(collection.aggregate(pipeline))
        return {r["_id"]: r["count"] for r in results if r["_id"]}

    def get_sentiment_over_time(self, days: int = 7, hashtag: Optional[str] = None) -> list[dict]:
        """Get sentiment counts grouped by day."""
        collection = self.get_collection("sentiment_results")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        match = {"analyzed_at": {"$gte": cutoff}}
        if hashtag:
            match["source_hashtag"] = hashtag

        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$analyzed_at"}},
                        "sentiment": "$sentiment",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.date": 1}},
        ]
        return list(collection.aggregate(pipeline))

    def get_top_keywords(self, sentiment: Optional[str] = None, limit: int = 20) -> list[dict]:
        """Get most frequent keywords from sentiment results."""
        collection = self.get_collection("sentiment_results")
        match = {}
        if sentiment:
            match["sentiment"] = sentiment

        pipeline = []
        if match:
            pipeline.append({"$match": match})
        pipeline.extend([
            {"$unwind": "$keywords"},
            {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
            {"$sort": {"count": DESCENDING}},
            {"$limit": limit},
        ])
        return list(collection.aggregate(pipeline))

    # -----------------------------------------------------------------
    # Hashtag Metrics
    # -----------------------------------------------------------------

    def upsert_hashtag_metrics(self, metrics: list[dict]) -> int:
        """Upsert hashtag aggregated metrics."""
        if not metrics:
            return 0

        collection = self.get_collection("hashtag_metrics")
        operations = []

        for m in metrics:
            m["updated_at"] = datetime.now(timezone.utc)
            operations.append(
                UpdateOne(
                    {"hashtag": m["hashtag"], "period_start": m.get("period_start", datetime.now(timezone.utc))},
                    {"$set": m},
                    upsert=True,
                )
            )

        try:
            res = collection.bulk_write(operations, ordered=False)
            total = res.upserted_count + res.modified_count
            logger.info(f"Upserted {total} hashtag metrics")
            return total
        except BulkWriteError as e:
            logger.warning(f"Hashtag metrics bulk write error: {e.details}")
            return 0

    def get_trending_hashtags(self, limit: int = 20) -> list[dict]:
        """Get hashtags ranked by trend score."""
        collection = self.get_collection("hashtag_metrics")
        pipeline = [
            {"$sort": {"updated_at": DESCENDING}},
            {
                "$group": {
                    "_id": "$hashtag",
                    "post_count": {"$first": "$post_count"},
                    "trend_score": {"$first": "$trend_score"},
                    "avg_sentiment": {"$first": "$avg_sentiment"},
                    "positive_ratio": {"$first": "$positive_ratio"},
                    "negative_ratio": {"$first": "$negative_ratio"},
                    "top_keywords": {"$first": "$top_keywords"},
                    "updated_at": {"$first": "$updated_at"},
                }
            },
            {"$sort": {"trend_score": DESCENDING}},
            {"$limit": limit},
        ]
        return list(collection.aggregate(pipeline))

    def get_hashtag_activity(self, hashtag: str, days: int = 7) -> list[dict]:
        """Get daily post counts for a hashtag."""
        collection = self.get_collection("instagram_posts")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        pipeline = [
            {"$match": {"source_hashtag": hashtag, "timestamp": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return list(collection.aggregate(pipeline))

    def get_hourly_activity(self, hashtag: Optional[str] = None, days: int = 7) -> list[dict]:
        """Get hourly post distribution."""
        collection = self.get_collection("instagram_posts")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        match = {"timestamp": {"$gte": cutoff}}
        if hashtag:
            match["source_hashtag"] = hashtag

        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": {"$hour": "$timestamp"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return list(collection.aggregate(pipeline))

    def get_engagement_leaderboard(self, limit: int = 20) -> list[dict]:
        """Get hashtags ranked by engagement rate."""
        collection = self.get_collection("instagram_posts")
        pipeline = [
            {
                "$group": {
                    "_id": "$source_hashtag",
                    "total_posts": {"$sum": 1},
                    "total_likes": {"$sum": {"$ifNull": ["$likes_count", 0]}},
                    "total_comments": {"$sum": {"$ifNull": ["$comments_count", 0]}},
                    "avg_likes": {"$avg": {"$ifNull": ["$likes_count", 0]}},
                    "avg_comments": {"$avg": {"$ifNull": ["$comments_count", 0]}},
                    "max_likes": {"$max": {"$ifNull": ["$likes_count", 0]}},
                }
            }
        ]
        results = list(collection.aggregate(pipeline))
        processed = []
        for r in results:
            tag = r.get("_id")
            if not tag:
                continue
            total_p = r.get("total_posts", 0)
            t_likes = r.get("total_likes", 0)
            t_comments = r.get("total_comments", 0)
            rate = round((t_likes + t_comments) / max(total_p, 1), 2)
            processed.append({
                "hashtag": tag,
                "total_posts": total_p,
                "total_likes": t_likes,
                "total_comments": t_comments,
                "avg_likes": round(float(r.get("avg_likes") or 0.0), 1),
                "avg_comments": round(float(r.get("avg_comments") or 0.0), 1),
                "max_likes": r.get("max_likes", 0),
                "engagement_rate": rate,
            })
        processed.sort(key=lambda x: x["engagement_rate"], reverse=True)
        return processed[:limit]

    def get_likes_vs_comments(self, hashtag: Optional[str] = None, limit: int = 150) -> list[dict]:
        """Get likes vs comments data points for scatter visualization."""
        collection = self.get_collection("instagram_posts")
        query: dict[str, Any] = {}
        if hashtag:
            query["source_hashtag"] = hashtag

        projection = {
            "_id": 0,
            "post_id": 1,
            "source_hashtag": 1,
            "likes_count": 1,
            "comments_count": 1,
            "media_type": 1,
            "caption": 1,
            "timestamp": 1,
        }
        items = list(collection.find(query, projection).sort("timestamp", DESCENDING).limit(limit))
        for item in items:
            item["likes_count"] = item.get("likes_count") or 0
            item["comments_count"] = item.get("comments_count") or 0
        return items

    def get_engagement_summary(self) -> dict:
        """Get platform-wide engagement summary metrics."""
        collection = self.get_collection("instagram_posts")
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_posts": {"$sum": 1},
                    "total_likes": {"$sum": {"$ifNull": ["$likes_count", 0]}},
                    "total_comments": {"$sum": {"$ifNull": ["$comments_count", 0]}},
                    "avg_likes": {"$avg": {"$ifNull": ["$likes_count", 0]}},
                    "avg_comments": {"$avg": {"$ifNull": ["$comments_count", 0]}},
                }
            }
        ]
        results = list(collection.aggregate(pipeline))
        if results:
            r = results[0]
            total_p = r.get("total_posts", 0)
            total_eng = r.get("total_likes", 0) + r.get("total_comments", 0)
            return {
                "total_posts": total_p,
                "total_likes": r.get("total_likes") or 0,
                "total_comments": r.get("total_comments") or 0,
                "avg_likes": round(float(r.get("avg_likes") or 0.0), 1),
                "avg_comments": round(float(r.get("avg_comments") or 0.0), 1),
                "avg_engagement_rate": round(float(total_eng / max(total_p, 1)), 2),
            }
        return {
            "total_posts": 0, "total_likes": 0, "total_comments": 0,
            "avg_likes": 0.0, "avg_comments": 0.0, "avg_engagement_rate": 0.0,
        }

    # -----------------------------------------------------------------
    # Collection Runs
    # -----------------------------------------------------------------

    def create_collection_run(self, hashtags: list[str], is_demo: bool = False) -> str:
        """Create a new collection run record. Returns the run_id."""
        run_id = str(uuid.uuid4())[:8]
        collection = self.get_collection("collection_runs")
        collection.insert_one({
            "run_id": run_id,
            "hashtags": hashtags,
            "posts_collected": 0,
            "status": "running",
            "error_message": "",
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "is_demo": is_demo,
        })
        return run_id

    def complete_collection_run(self, run_id: str, posts_collected: int, status: str = "completed", error: str = ""):
        """Mark a collection run as complete."""
        collection = self.get_collection("collection_runs")
        collection.update_one(
            {"run_id": run_id},
            {"$set": {
                "posts_collected": posts_collected,
                "status": status,
                "error_message": error,
                "completed_at": datetime.now(timezone.utc),
            }},
        )

    def get_latest_collection_run(self) -> Optional[dict]:
        """Get the most recent collection run."""
        collection = self.get_collection("collection_runs")
        result = collection.find_one(
            {}, {"_id": 0}, sort=[("started_at", DESCENDING)]
        )
        return result

    def get_collection_runs(self, limit: int = 10) -> list[dict]:
        """Get recent collection runs."""
        collection = self.get_collection("collection_runs")
        return list(
            collection.find({}, {"_id": 0})
            .sort("started_at", DESCENDING)
            .limit(limit)
        )

    def get_recent_errors(self, limit: int = 5) -> list[str]:
        """Get recent error messages from collection runs."""
        collection = self.get_collection("collection_runs")
        runs = list(
            collection.find(
                {"status": "failed", "error_message": {"$ne": ""}},
                {"_id": 0, "error_message": 1, "started_at": 1},
            )
            .sort("started_at", DESCENDING)
            .limit(limit)
        )
        return [r["error_message"] for r in runs]

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB connection closed")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance
_db_instance: Optional[MongoDBManager] = None


def get_db() -> MongoDBManager:
    """Get or create the singleton database manager."""
    global _db_instance
    if _db_instance is None:
        _db_instance = MongoDBManager()
        _db_instance.connect()
        _db_instance.setup_collections()
    return _db_instance
