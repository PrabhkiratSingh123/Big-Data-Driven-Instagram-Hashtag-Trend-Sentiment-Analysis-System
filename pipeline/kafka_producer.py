"""
SocialTrendML — Kafka Producer
Publishes Instagram post events to a Kafka topic for downstream processing.
"""

import json
import logging
import time
from typing import Optional

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class PostEventProducer:
    """
    Publishes normalized Instagram post events to Kafka.
    Handles serialization, partitioning, and delivery confirmation.
    """

    def __init__(self):
        self.settings = get_settings()
        self._producer = None
        self._metrics = {"sent": 0, "failed": 0}

    def _connect(self):
        """Connect to Kafka with retry logic."""
        from kafka import KafkaProducer
        from kafka.errors import NoBrokersAvailable

        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self.settings.kafka_bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    retries=3,
                    acks="all",
                    compression_type="gzip",
                )
                logger.info(f"Connected to Kafka at {self.settings.kafka_bootstrap_servers}")
                return
            except NoBrokersAvailable:
                logger.warning(f"Kafka not available (attempt {attempt}/{max_retries})")
                time.sleep(5 * attempt)

        raise ConnectionError("Failed to connect to Kafka")

    def publish_posts(self, posts: list[dict]) -> int:
        """
        Publish a batch of posts to Kafka.
        Returns count of successfully published messages.
        """
        if self._producer is None:
            self._connect()

        sent = 0
        for post in posts:
            key = post.get("source_hashtag", post.get("post_id", "unknown"))
            try:
                future = self._producer.send(
                    self.settings.kafka_topic,
                    key=key,
                    value=post,
                )
                future.add_callback(lambda _: None)
                future.add_errback(lambda e: logger.error(f"Kafka delivery failed: {e}"))
                sent += 1
            except Exception as e:
                logger.error(f"Failed to publish post {post.get('post_id')}: {e}")
                self._metrics["failed"] += 1

        self._producer.flush(timeout=30)
        self._metrics["sent"] += sent
        logger.info(f"Published {sent}/{len(posts)} posts to Kafka topic '{self.settings.kafka_topic}'")
        return sent

    def close(self):
        if self._producer:
            self._producer.close(timeout=10)
            self._producer = None
            logger.info(f"Kafka producer closed. Total sent: {self._metrics['sent']}, failed: {self._metrics['failed']}")

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *args):
        self.close()
