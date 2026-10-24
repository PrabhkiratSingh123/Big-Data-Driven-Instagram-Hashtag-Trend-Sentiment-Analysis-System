"""
MongoDB Setup Script
Initializes the instagram_analytics database with collections and indexes.
Run this once before starting the pipeline when using local MongoDB (Compass).

Usage:
    python setup_mongodb.py
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, CollectionInvalid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("mongo_setup")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "instagram_analytics")


def setup_database():
    """Create collections, indexes, and validation rules."""
    logger.info("🚀 Connecting to MongoDB...")

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        logger.info(f"✅ Connected to MongoDB at {MONGO_URI}")
    except ConnectionFailure as e:
        logger.error(
            f"❌ Cannot connect to MongoDB at {MONGO_URI}\n"
            f"   Make sure MongoDB is running (check MongoDB Compass).\n"
            f"   Error: {e}"
        )
        sys.exit(1)

    db = client[MONGO_DB]

    # ---- Create Collections ----
    collections_to_create = [
        "raw_posts",
        "hashtag_trends",
        "engagement_metrics",
        "sentiment_scores",
    ]

    for coll_name in collections_to_create:
        try:
            db.create_collection(coll_name)
            logger.info(f"   Created collection: {coll_name}")
        except CollectionInvalid:
            logger.info(f"   Collection already exists: {coll_name}")

    # ---- Create Indexes ----
    logger.info("📑 Creating indexes...")

    # raw_posts
    db.raw_posts.create_index("post_id", unique=True, name="idx_post_id")
    db.raw_posts.create_index(
        [("timestamp", -1), ("hashtags", 1)], name="idx_timestamp_hashtags"
    )
    db.raw_posts.create_index("username", name="idx_username")
    db.raw_posts.create_index([("ingested_at", -1)], name="idx_ingested_at")

    # hashtag_trends
    db.hashtag_trends.create_index(
        [("hashtag", 1), ("window_start", -1), ("window_duration_min", 1)],
        unique=True,
        name="idx_hashtag_window",
    )
    db.hashtag_trends.create_index(
        [("window_start", -1)], name="idx_window_start"
    )
    db.hashtag_trends.create_index([("count", -1)], name="idx_count")

    # engagement_metrics
    db.engagement_metrics.create_index(
        "hashtag", unique=True, name="idx_hashtag"
    )
    db.engagement_metrics.create_index(
        [("engagement_rate", -1)], name="idx_engagement_rate"
    )

    # sentiment_scores
    db.sentiment_scores.create_index(
        "post_id", unique=True, name="idx_post_id"
    )
    db.sentiment_scores.create_index(
        [("timestamp", -1), ("sentiment_label", 1)],
        name="idx_timestamp_sentiment",
    )
    db.sentiment_scores.create_index(
        "sentiment_label", name="idx_sentiment_label"
    )

    logger.info("✅ All indexes created successfully")

    # ---- Summary ----
    logger.info("")
    logger.info("=" * 55)
    logger.info(f"  Database: {MONGO_DB}")
    logger.info(f"  Collections: {', '.join(collections_to_create)}")
    logger.info(f"  Open MongoDB Compass → connect to {MONGO_URI}")
    logger.info(f"  Navigate to '{MONGO_DB}' to view collections")
    logger.info("=" * 55)

    client.close()
    logger.info("🎉 MongoDB setup complete!")


if __name__ == "__main__":
    setup_database()
