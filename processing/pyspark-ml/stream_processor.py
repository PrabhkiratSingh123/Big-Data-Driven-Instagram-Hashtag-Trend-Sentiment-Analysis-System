"""
Streaming Sentiment Processor
Consumes Instagram posts from Kafka, applies the trained MLlib sentiment model,
and writes sentiment scores to MongoDB.

Requires: trained model in processing/pyspark-ml/model/sentiment_pipeline/
(run sentiment_model.py first to train)
"""

import os
import sys
import logging
from datetime import datetime, timezone

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, from_json, udf, current_timestamp,
    to_timestamp, lit, array, struct,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    ArrayType, DoubleType,
)
from pyspark.ml import PipelineModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("stream_processor")

# Configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "instagram-posts")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "instagram_analytics")
MODEL_DIR = os.getenv(
    "MODEL_DIR",
    os.path.join(os.path.dirname(__file__), "model", "sentiment_pipeline"),
)
CHECKPOINT_DIR = os.getenv(
    "CHECKPOINT_DIR", "/tmp/spark-checkpoints/sentiment"
)

# Schema matching the Kafka producer's JSON format
POST_SCHEMA = StructType([
    StructField("post_id", StringType(), False),
    StructField("username", StringType(), True),
    StructField("caption", StringType(), True),
    StructField("hashtags", ArrayType(StringType()), True),
    StructField("timestamp", StringType(), False),
    StructField("media_type", StringType(), True),
    StructField("likes_count", IntegerType(), True),
    StructField("comments_count", IntegerType(), True),
    StructField("media_url", StringType(), True),
    StructField("_sentiment_label", StringType(), True),
])


def create_spark_session() -> SparkSession:
    """Create a Spark session configured for Kafka and MongoDB."""
    return SparkSession.builder \
        .appName("InstagramSentimentProcessor") \
        .config("spark.mongodb.write.connection.uri", f"{MONGO_URI}/{MONGO_DB}") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_DIR) \
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                "org.mongodb.spark:mongo-spark-connector_2.12:10.2.1") \
        .getOrCreate()


def write_to_mongodb(batch_df: DataFrame, batch_id: int):
    """
    Write a micro-batch of sentiment scores to MongoDB.
    Called by foreachBatch on the streaming query.
    """
    if batch_df.isEmpty():
        return

    count = batch_df.count()
    logger.info(f"🧠 Writing sentiment batch #{batch_id} ({count} posts)")

    # Select and rename columns for MongoDB
    output_df = batch_df.select(
        col("post_id"),
        col("caption"),
        col("text"),  # cleaned text used for prediction
        col("predicted_label").alias("sentiment_label"),
        # Extract max probability as confidence score
        col("probability").getItem(0).alias("sentiment_score"),
        col("hashtags"),
        col("event_time").alias("timestamp"),
        current_timestamp().alias("processed_at"),
    )

    # Write to MongoDB
    output_df.write \
        .format("mongodb") \
        .mode("append") \
        .option("connection.uri", f"{MONGO_URI}/{MONGO_DB}") \
        .option("collection", "sentiment_scores") \
        .save()


def run_streaming():
    """Main streaming pipeline: Kafka → Sentiment Model → MongoDB."""
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    logger.info("=" * 60)
    logger.info("🧠 Sentiment Stream Processor Starting")
    logger.info(f"   Kafka:      {KAFKA_BOOTSTRAP}")
    logger.info(f"   Topic:      {KAFKA_TOPIC}")
    logger.info(f"   MongoDB:    {MONGO_URI}/{MONGO_DB}")
    logger.info(f"   Model:      {MODEL_DIR}")
    logger.info("=" * 60)

    # Load trained model
    try:
        model = PipelineModel.load(MODEL_DIR)
        logger.info("✅ Sentiment model loaded successfully")
    except Exception as e:
        logger.error(
            f"❌ Failed to load model from {MODEL_DIR}. "
            f"Run sentiment_model.py first to train the model.\n"
            f"Error: {e}"
        )
        sys.exit(1)

    # Read from Kafka
    raw_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    # Parse JSON
    posts_stream = raw_stream \
        .selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), POST_SCHEMA).alias("post")) \
        .select(
            col("post.post_id"),
            col("post.caption"),
            col("post.hashtags"),
            to_timestamp(col("post.timestamp")).alias("event_time"),
        ) \
        .withWatermark("event_time", "10 minutes")

    # Prepare text column for the model (the model expects a 'text' column)
    posts_with_text = posts_stream.withColumn("text", col("caption"))

    # Apply sentiment model in foreachBatch
    query = posts_with_text.writeStream \
        .outputMode("append") \
        .foreachBatch(lambda batch_df, batch_id: process_batch(batch_df, batch_id, model)) \
        .option("checkpointLocation", f"{CHECKPOINT_DIR}/sentiment-scores") \
        .trigger(processingTime="15 seconds") \
        .start()

    logger.info("📊 Sentiment streaming started. Awaiting termination...")
    query.awaitTermination()


def process_batch(batch_df: DataFrame, batch_id: int, model: PipelineModel):
    """Process a micro-batch: apply model and write to MongoDB."""
    if batch_df.isEmpty():
        return

    # Apply sentiment model
    predictions = model.transform(batch_df)

    # Write results to MongoDB
    write_to_mongodb(predictions, batch_id)


if __name__ == "__main__":
    run_streaming()
