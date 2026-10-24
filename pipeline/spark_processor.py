"""
SocialTrendML — PySpark Processor
Distributed processing for trend analytics using PySpark.
Reads from MongoDB, performs aggregation, and writes metrics back.

When Spark is unavailable, falls back to local Pandas processing.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import get_settings
from backend.app.database.mongodb import get_db
from backend.app.ml.sentiment import calculate_trend_score, extract_keywords

logger = logging.getLogger(__name__)


def run_spark_aggregation():
    """
    Run PySpark aggregation job on instagram_posts collection.
    Computes hashtag metrics, trend scores, and time-series data.

    Falls back to local Pandas processing if Spark is unavailable.
    """
    try:
        return _run_with_spark()
    except Exception as e:
        logger.warning(f"Spark processing unavailable ({e}), using local fallback")
        return _run_local_fallback()


def _run_with_spark():
    """Full PySpark processing pipeline."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        StructType, StructField, StringType, TimestampType,
        ArrayType, BooleanType,
    )

    settings = get_settings()

    spark = (
        SparkSession.builder
        .appName("SocialTrendML-Processor")
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.mongodb.input.uri", f"{settings.mongodb_uri}/{settings.mongodb_database}.instagram_posts")
        .config("spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:10.2.1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    logger.info("Loading posts from MongoDB via Spark...")

    # Read from MongoDB
    df = (
        spark.read
        .format("mongodb")
        .option("uri", f"{settings.mongodb_uri}/{settings.mongodb_database}.instagram_posts")
        .load()
    )

    if df.count() == 0:
        logger.info("No posts to process")
        spark.stop()
        return {"processed": 0}

    # --- Aggregation: posts per hashtag ---
    hashtag_counts = (
        df.groupBy("source_hashtag")
        .agg(
            F.count("*").alias("post_count"),
            F.min("timestamp").alias("earliest"),
            F.max("timestamp").alias("latest"),
        )
        .collect()
    )

    # --- Time-series: daily counts per hashtag ---
    daily_counts = (
        df.withColumn("date", F.date_format("timestamp", "yyyy-MM-dd"))
        .groupBy("source_hashtag", "date")
        .count()
        .orderBy("source_hashtag", "date")
        .collect()
    )

    # --- Hourly distribution ---
    hourly_dist = (
        df.withColumn("hour", F.hour("timestamp"))
        .groupBy("hour")
        .count()
        .orderBy("hour")
        .collect()
    )

    # --- Caption cleaning & keyword extraction (on driver for simplicity) ---
    # For large-scale, this should use UDFs
    db = get_db()
    metrics = []
    for row in hashtag_counts:
        hashtag = row["source_hashtag"]
        count = row["post_count"]

        # Get sentiment data from MongoDB (already computed)
        sentiment_dist = db.get_sentiment_distribution(hashtag=hashtag)
        total_s = sum(sentiment_dist.values()) or 1

        avg_sent = (sentiment_dist.get("positive", 0) - sentiment_dist.get("negative", 0)) / total_s

        # Get recent vs older for trend score
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        posts_data = db.get_posts(hashtag=hashtag, limit=500)
        recent = sum(1 for p in posts_data if p.get("timestamp") and p["timestamp"] > cutoff)
        older = count - recent

        # Keywords
        all_kw = []
        for p in posts_data[:100]:
            all_kw.extend(extract_keywords(p.get("caption", "")))
        top_kw = [w for w, _ in Counter(all_kw).most_common(10)]

        metrics.append({
            "hashtag": hashtag,
            "post_count": count,
            "avg_sentiment": avg_sent,
            "positive_ratio": sentiment_dist.get("positive", 0) / total_s,
            "negative_ratio": sentiment_dist.get("negative", 0) / total_s,
            "neutral_ratio": sentiment_dist.get("neutral", 0) / total_s,
            "top_keywords": top_kw,
            "trend_score": calculate_trend_score(recent, older, avg_sent),
            "period_start": row["earliest"],
            "period_end": row["latest"],
        })

    # Store metrics
    if metrics:
        db.upsert_hashtag_metrics(metrics)

    total = sum(m["post_count"] for m in metrics)
    logger.info(f"Spark processing complete: {total} posts across {len(metrics)} hashtags")

    spark.stop()
    return {"processed": total, "hashtags": len(metrics), "engine": "spark"}


def _run_local_fallback():
    """Local fallback using Pandas when Spark is unavailable."""
    import pandas as pd

    db = get_db()
    hashtags = db.get_unique_hashtags()

    if not hashtags:
        logger.info("No hashtags to process")
        return {"processed": 0, "engine": "local_fallback"}

    metrics = []
    total_processed = 0

    for hashtag in hashtags:
        posts = db.get_posts(hashtag=hashtag, limit=1000)
        if not posts:
            continue

        df = pd.DataFrame(posts)
        count = len(df)
        total_processed += count

        # Sentiment distribution
        sentiment_dist = db.get_sentiment_distribution(hashtag=hashtag)
        total_s = sum(sentiment_dist.values()) or 1

        avg_sent = (sentiment_dist.get("positive", 0) - sentiment_dist.get("negative", 0)) / total_s

        # Recent vs older
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            recent = len(df[df["timestamp"] > cutoff])
        else:
            recent = 0
        older = count - recent

        # Keywords
        all_kw = []
        for caption in df.get("caption", pd.Series(dtype=str)).dropna():
            all_kw.extend(extract_keywords(caption))
        top_kw = [w for w, _ in Counter(all_kw).most_common(10)]

        earliest = df["timestamp"].min() if "timestamp" in df.columns else datetime.now(timezone.utc)
        latest = df["timestamp"].max() if "timestamp" in df.columns else datetime.now(timezone.utc)

        metrics.append({
            "hashtag": hashtag,
            "post_count": count,
            "avg_sentiment": avg_sent,
            "positive_ratio": sentiment_dist.get("positive", 0) / total_s,
            "negative_ratio": sentiment_dist.get("negative", 0) / total_s,
            "neutral_ratio": sentiment_dist.get("neutral", 0) / total_s,
            "top_keywords": top_kw,
            "trend_score": calculate_trend_score(recent, older, avg_sent),
            "period_start": earliest,
            "period_end": latest,
        })

    if metrics:
        db.upsert_hashtag_metrics(metrics)

    logger.info(f"Local processing complete: {total_processed} posts across {len(metrics)} hashtags")
    return {"processed": total_processed, "hashtags": len(metrics), "engine": "local_fallback"}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    )
    result = run_spark_aggregation()
    print(f"Processing result: {result}")
