"""
SocialTrendML — Kafka Consumer
Consumes Instagram post events from Kafka and processes them
through the sentiment analysis pipeline, storing results in MongoDB.
"""

import json
import logging
import signal
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import get_settings
from backend.app.database.mongodb import get_db
from backend.app.ml.sentiment import get_sentiment_analyzer

logger = logging.getLogger(__name__)


class PostEventConsumer:
    """
    Consumes posts from Kafka and runs them through the
    Spark ML sentiment analysis pipeline.
    """

    def __init__(self):
        self.settings = get_settings()
        self._consumer = None
        self._running = True
        self._db = get_db()
        self._analyzer = None
        self._batch_buffer = []
        self._batch_size = 20

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("Shutdown signal received")
        self._running = False

    def _connect(self):
        from kafka import KafkaConsumer

        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                self._consumer = KafkaConsumer(
                    self.settings.kafka_topic,
                    bootstrap_servers=self.settings.kafka_bootstrap_servers,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    group_id="socialtrendml-sentiment",
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    consumer_timeout_ms=5000,
                )
                logger.info(f"Connected to Kafka consumer on topic '{self.settings.kafka_topic}'")
                return
            except Exception as e:
                logger.warning(f"Kafka consumer connect attempt {attempt}: {e}")
                time.sleep(5 * attempt)

        raise ConnectionError("Failed to connect Kafka consumer")

    def run(self):
        """Main consumer loop."""
        logger.info("Starting Kafka consumer for sentiment processing...")
        self._connect()

        try:
            self._analyzer = get_sentiment_analyzer()
        except Exception as e:
            logger.error(f"Failed to initialize sentiment analyzer: {e}")
            return

        try:
            while self._running:
                try:
                    for message in self._consumer:
                        if not self._running:
                            break

                        post = message.value
                        self._batch_buffer.append(post)

                        if len(self._batch_buffer) >= self._batch_size:
                            self._process_batch()

                    # Process remaining buffer
                    if self._batch_buffer:
                        self._process_batch()

                except StopIteration:
                    # Consumer timeout — process any buffered items
                    if self._batch_buffer:
                        self._process_batch()
                    time.sleep(1)

        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            if self._batch_buffer:
                self._process_batch()
            if self._consumer:
                self._consumer.close()
            logger.info("Kafka consumer stopped")

    def _process_batch(self):
        """Process a batch of posts through sentiment analysis."""
        if not self._batch_buffer:
            return

        batch = self._batch_buffer[:]
        self._batch_buffer.clear()

        try:
            # Store posts
            self._db.upsert_posts(batch)

            # Run sentiment analysis
            results = self._analyzer.analyze_batch(batch)
            if results:
                self._db.upsert_sentiment_results(results)

            logger.info(f"Processed batch of {len(batch)} posts, {len(results)} sentiments")
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    )
    consumer = PostEventConsumer()
    consumer.run()
