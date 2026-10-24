"""
SocialTrendML — Core Configuration
Centralized settings using Pydantic BaseSettings for type-safe env var loading.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Instagram Graph API ---
    meta_access_token: str = Field(
        default="",
        validation_alias=AliasChoices("meta_access_token", "instagram_access_token"),
        description="Meta Graph API access token",
    )
    instagram_user_id: str = Field(
        default="17841448764193411",
        validation_alias=AliasChoices("instagram_user_id", "instagram_app_id"),
        description="Instagram Professional Account ID",
    )
    meta_graph_api_version: str = Field(default="v26.0", description="Graph API version")

    # --- MongoDB ---
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("mongodb_uri", "mongo_uri"),
        description="MongoDB connection string",
    )
    mongodb_database: str = Field(
        default="socialtrendml",
        validation_alias=AliasChoices("mongodb_database", "mongo_db"),
        description="MongoDB database name",
    )

    # --- Kafka ---
    kafka_bootstrap_servers: str = Field(default="localhost:9092", description="Kafka broker address")
    kafka_topic: str = Field(default="instagram-posts", description="Kafka topic for posts")

    # --- Collection ---
    collection_interval_seconds: int = Field(default=300, description="Polling interval in seconds")
    default_hashtags: str = Field(default="technology,artificialintelligence,datascience,sports")

    # --- FastAPI ---
    fastapi_host: str = Field(default="0.0.0.0")
    fastapi_port: int = Field(default=8000)

    # --- Logging ---
    log_level: str = Field(default="INFO")

    @property
    def graph_api_base_url(self) -> str:
        ver = self.meta_graph_api_version.strip()
        if not ver.startswith("v"):
            ver = f"v{ver}"
        return f"https://graph.facebook.com/{ver}"

    @property
    def is_api_configured(self) -> bool:
        return bool(self.meta_access_token)

    @property
    def default_hashtags_list(self) -> list[str]:
        return [h.strip() for h in self.default_hashtags.split(",") if h.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance, searching for .env in project root and parent directories."""
    # Try finding .env in workspace root (4 levels up from this file)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(current_dir, "..", "..", "..", ".env"),  # root cluster_project/.env
        os.path.join(current_dir, "..", "..", ".env"),        # backend/.env
        os.path.join(os.getcwd(), ".env"),
    ]
    for env_candidate in candidates:
        norm_path = os.path.normpath(env_candidate)
        if os.path.isfile(norm_path):
            return Settings(_env_file=norm_path)
    return Settings()
