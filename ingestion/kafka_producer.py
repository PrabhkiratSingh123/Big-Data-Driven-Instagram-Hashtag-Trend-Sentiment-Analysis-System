"""
Kafka Producer for Instagram Posts
Publishes Instagram post data (mock or real) to a Kafka topic.
Includes delivery callbacks, error handling, and metrics tracking.
"""

import json
import time
import signal
import logging
import sys
import os

# Add parent directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable

from config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_POSTS,
    KAFKA_PRODUCER_RETRIES,
    KAFKA_BATCH_SIZE,
    KAFKA_LINGER_MS,
    BATCH_SIZE,
    BATCH_INTERVAL,
    MONGO_URI,
    MONGO_DB,
    LOG_LEVEL,
    LOG_FORMAT,
)
from mock_data_generator import generate_batch
from storage.mongo_client import MongoDBClient

# --- Logging Setup ---
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("kafka_producer")


class InstagramKafkaProducer:
    """
    Publishes Instagram post data to Kafka with delivery confirmation,
    retry logic, and optional MongoDB raw storage.
    """

    def __init__(self):
        self._running = True
        self._producer = None
        self._mongo = None
        self._metrics = {
            "total_sent": 0,
            "total_failed": 0,
            "total_batches": 0,
            "start_time": time.time(),
        }

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info("Shutdown signal received — finishing current batch...")
        self._running = False

    def _connect_kafka(self) -> KafkaProducer:
        """Connect to Kafka with retry logic."""
        max_retries = 10
        retry_delay = 5

        for attempt in range(1, max_retries + 1):
            try:
                producer = KafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    retries=KAFKA_PRODUCER_RETRIES,
                    batch_size=KAFKA_BATCH_SIZE,
                    linger_ms=KAFKA_LINGER_MS,
                    acks="all",
                    compression_type="gzip",
                    max_request_size=1048576,
                )
                logger.info(
                    f"Connected to Kafka broker at {KAFKA_BOOTSTRAP_SERVERS}"
                )
                return producer
            except NoBrokersAvailable:
                logger.warning(
                    f"Kafka broker not available (attempt {attempt}/{max_retries}). "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)

        raise ConnectionError(
            f"Failed to connect to Kafka after {max_retries} attempts"
        )

    def _connect_mongo(self) -> MongoDBClient:
        """Connect to MongoDB for raw post storage."""
        try:
            client = MongoDBClient(uri=MONGO_URI, db_name=MONGO_DB)
            client.connect()
            logger.info("Connected to MongoDB for raw post storage")
            return client
        except Exception as e:
            logger.warning(f"MongoDB connection failed (non-fatal): {e}")
            return None

    def _on_success(self, record_metadata):
        """Callback for successful message delivery."""
        logger.debug(
            f"Delivered to {record_metadata.topic}[{record_metadata.partition}] "
            f"@ offset {record_metadata.offset}"
        )
        self._metrics["total_sent"] += 1

    def _on_error(self, exception):
        """Callback for failed message delivery."""
        logger.error(f"Delivery failed: {exception}")
        self._metrics["total_failed"] += 1

    def _publish_batch(self, posts: list[dict]):
        """Publish a batch of posts to Kafka and optionally store in MongoDB."""
        for post in posts:
            # Use first hashtag as partition key for co-location
            key = post["hashtags"][0] if post["hashtags"] else post["post_id"]

            future = self._producer.send(
                KAFKA_TOPIC_POSTS,
                key=key,
                value=post,
            )
            future.add_callback(self._on_success)
            future.add_errback(self._on_error)

        # Ensure all messages are sent
        self._producer.flush(timeout=30)

        # Store raw posts in MongoDB
        if self._mongo:
            try:
                # Remove the ground truth label before storing
                mongo_posts = []
                for post in posts:
                    p = dict(post)
                    p.pop("_sentiment_label", None)
                    mongo_posts.append(p)
                self._mongo.insert_raw_posts(mongo_posts)
            except Exception as e:
                logger.warning(f"MongoDB insert failed (non-fatal): {e}")

        self._metrics["total_batches"] += 1

    def _log_metrics(self):
        """Log production metrics."""
        elapsed = time.time() - self._metrics["start_time"]
        rate = (
            self._metrics["total_sent"] / elapsed if elapsed > 0 else 0
        )
        logger.info(
            f"📊 Metrics | "
            f"Batches: {self._metrics['total_batches']} | "
            f"Sent: {self._metrics['total_sent']} | "
            f"Failed: {self._metrics['total_failed']} | "
            f"Rate: {rate:.1f} msg/s | "
            f"Uptime: {elapsed:.0f}s"
        )

    def run(self):
        """Main production loop — generates and publishes batches continuously."""
        logger.info("=" * 60)
        logger.info("🚀 Instagram Kafka Producer Starting")
        logger.info(f"   Broker:   {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info(f"   Topic:    {KAFKA_TOPIC_POSTS}")
        logger.info(f"   Batch:    {BATCH_SIZE} posts every {BATCH_INTERVAL}s")
        logger.info("=" * 60)

        self._producer = self._connect_kafka()
        self._mongo = self._connect_mongo()

        try:
            while self._running:
                # Generate batch
                posts = generate_batch(batch_size=BATCH_SIZE)
                logger.info(
                    f"📤 Publishing batch of {len(posts)} posts to "
                    f"'{KAFKA_TOPIC_POSTS}'..."
                )

                # Publish
                self._publish_batch(posts)

                # Log metrics every 5 batches
                if self._metrics["total_batches"] % 5 == 0:
                    self._log_metrics()

                # Wait for next batch
                if self._running:
                    logger.info(
                        f"⏳ Waiting {BATCH_INTERVAL}s until next batch..."
                    )
                    # Sleep in small intervals for responsive shutdown
                    for _ in range(BATCH_INTERVAL):
                        if not self._running:
                            break
                        time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self._log_metrics()
            if self._producer:
                self._producer.close(timeout=10)
                logger.info("Kafka producer closed")
            if self._mongo:
                self._mongo.close()
            logger.info("🛑 Producer shutdown complete")


if __name__ == "__main__":
    producer = InstagramKafkaProducer()
    producer.run()
