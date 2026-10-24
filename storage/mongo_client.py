"""
Shared MongoDB Client Utilities
Provides connection management and common database operations
for the Instagram Analytics pipeline.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import (
    ConnectionFailure,
    BulkWriteError,
    DuplicateKeyError,
    PyMongoError,
)

logger = logging.getLogger(__name__)


class MongoDBClient:
    """Thread-safe MongoDB client wrapper with connection pooling."""

    def __init__(
        self,
        uri: Optional[str] = None,
        db_name: Optional[str] = None,
        max_pool_size: int = 50,
    ):
        self.uri = uri or os.getenv(
            "MONGO_URI", "mongodb://localhost:27017"
        )
        self.db_name = db_name or os.getenv("MONGO_DB", "instagram_analytics")
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._max_pool_size = max_pool_size

    def connect(self) -> Database:
        """Establish connection to MongoDB with connection pooling."""
        if self._client is None:
            try:
                self._client = MongoClient(
                    self.uri,
                    maxPoolSize=self._max_pool_size,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    retryWrites=True,
                )
                # Verify connection
                self._client.admin.command("ping")
                self._db = self._client[self.db_name]
                logger.info(f"Connected to MongoDB: {self.db_name}")
            except ConnectionFailure as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return self._db

    @property
    def db(self) -> Database:
        """Get the database instance, connecting if necessary."""
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, name: str) -> Collection:
        """Get a collection by name."""
        return self.db[name]

    # ----- Raw Posts -----

    def insert_raw_posts(self, posts: list[dict[str, Any]]) -> int:
        """Insert raw posts with duplicate handling. Returns count of inserted docs."""
        if not posts:
            return 0

        collection = self.get_collection("raw_posts")
        now = datetime.now(timezone.utc)

        for post in posts:
            post.setdefault("ingested_at", now)
            if isinstance(post.get("timestamp"), str):
                post["timestamp"] = datetime.fromisoformat(
                    post["timestamp"].replace("Z", "+00:00")
                )

        try:
            result = collection.insert_many(posts, ordered=False)
            inserted = len(result.inserted_ids)
            logger.info(f"Inserted {inserted} raw posts")
            return inserted
        except BulkWriteError as e:
            inserted = e.details.get("nInserted", 0)
            logger.warning(
                f"Bulk write: {inserted} inserted, "
                f"{len(e.details.get('writeErrors', []))} duplicates skipped"
            )
            return inserted

    # ----- Hashtag Trends -----

    def upsert_hashtag_trends(self, trends: list[dict[str, Any]]) -> int:
        """Upsert hashtag trend data using bulk operations."""
        if not trends:
            return 0

        collection = self.get_collection("hashtag_trends")
        operations = []

        for trend in trends:
            trend["updated_at"] = datetime.now(timezone.utc)
            filter_key = {
                "hashtag": trend["hashtag"],
                "window_start": trend["window_start"],
                "window_duration_min": trend.get("window_duration_min", 5),
            }
            operations.append(
                UpdateOne(filter_key, {"$set": trend}, upsert=True)
            )

        try:
            result = collection.bulk_write(operations, ordered=False)
            modified = result.modified_count + result.upserted_count
            logger.info(f"Upserted {modified} hashtag trend records")
            return modified
        except BulkWriteError as e:
            logger.error(f"Hashtag trends bulk write error: {e.details}")
            return 0

    # ----- Engagement Metrics -----

    def upsert_engagement_metrics(self, metrics: list[dict[str, Any]]) -> int:
        """Upsert engagement metrics per hashtag."""
        if not metrics:
            return 0

        collection = self.get_collection("engagement_metrics")
        operations = []

        for metric in metrics:
            metric["updated_at"] = datetime.now(timezone.utc)
            operations.append(
                UpdateOne(
                    {"hashtag": metric["hashtag"]},
                    {"$set": metric},
                    upsert=True,
                )
            )

        try:
            result = collection.bulk_write(operations, ordered=False)
            modified = result.modified_count + result.upserted_count
            logger.info(f"Upserted {modified} engagement metric records")
            return modified
        except BulkWriteError as e:
            logger.error(f"Engagement metrics bulk write error: {e.details}")
            return 0

    # ----- Sentiment Scores -----

    def insert_sentiment_scores(self, scores: list[dict[str, Any]]) -> int:
        """Insert sentiment scores with duplicate handling."""
        if not scores:
            return 0

        collection = self.get_collection("sentiment_scores")
        now = datetime.now(timezone.utc)

        for score in scores:
            score.setdefault("processed_at", now)

        try:
            result = collection.insert_many(scores, ordered=False)
            inserted = len(result.inserted_ids)
            logger.info(f"Inserted {inserted} sentiment scores")
            return inserted
        except BulkWriteError as e:
            inserted = e.details.get("nInserted", 0)
            logger.warning(
                f"Sentiment scores: {inserted} inserted, "
                f"{len(e.details.get('writeErrors', []))} duplicates skipped"
            )
            return inserted

    # ----- Query Helpers -----

    def get_top_hashtags(
        self, window_duration_min: int = 5, limit: int = 20
    ) -> list[dict]:
        """Get top trending hashtags from the most recent window."""
        collection = self.get_collection("hashtag_trends")
        pipeline = [
            {"$match": {"window_duration_min": window_duration_min}},
            {"$sort": {"window_start": -1}},
            {
                "$group": {
                    "_id": "$hashtag",
                    "latest_count": {"$first": "$count"},
                    "latest_velocity": {"$first": "$velocity"},
                    "window_start": {"$first": "$window_start"},
                }
            },
            {"$sort": {"latest_count": -1}},
            {"$limit": limit},
        ]
        return list(collection.aggregate(pipeline))

    def get_sentiment_distribution(
        self, hours: int = 24
    ) -> list[dict]:
        """Get sentiment distribution over the last N hours."""
        collection = self.get_collection("sentiment_scores")
        cutoff = datetime.now(timezone.utc)
        pipeline = [
            {
                "$group": {
                    "_id": "$sentiment_label",
                    "count": {"$sum": 1},
                    "avg_score": {"$avg": "$sentiment_score"},
                }
            },
            {"$sort": {"count": -1}},
        ]
        return list(collection.aggregate(pipeline))

    def get_engagement_leaderboard(self, limit: int = 20) -> list[dict]:
        """Get hashtags with highest engagement rates."""
        collection = self.get_collection("engagement_metrics")
        return list(
            collection.find(
                {}, {"_id": 0}
            )
            .sort("engagement_rate", -1)
            .limit(limit)
        )

    # ----- Lifecycle -----

    def close(self):
        """Close the MongoDB connection."""
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
