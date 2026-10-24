"""
Configuration module for the Instagram data ingestion pipeline.
Reads from environment variables with sensible defaults for local development.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Kafka Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_POSTS = os.getenv("KAFKA_TOPIC_POSTS", "instagram-posts")
KAFKA_PRODUCER_RETRIES = int(os.getenv("KAFKA_PRODUCER_RETRIES", "3"))
KAFKA_BATCH_SIZE = int(os.getenv("KAFKA_BATCH_SIZE", "16384"))
KAFKA_LINGER_MS = int(os.getenv("KAFKA_LINGER_MS", "10"))

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "instagram_analytics")

# --- Ingestion Settings ---
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
BATCH_INTERVAL = int(os.getenv("BATCH_INTERVAL", "30"))  # seconds

# --- Instagram Graph API (Future Integration) ---
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
INSTAGRAM_API_BASE_URL = "https://graph.instagram.com/v18.0"

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
