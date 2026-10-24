"""Unit tests for configuration loading and environment variables."""

import os
from backend.app.core.config import Settings, get_settings


def test_settings_default_values():
    settings = Settings(_env_file=None)
    assert settings.fastapi_port == 8000
    assert settings.meta_graph_api_version == "v26.0"
    assert "technology" in settings.default_hashtags_list


def test_settings_graph_api_url():
    settings = Settings(_env_file=None)
    assert settings.graph_api_base_url == "https://graph.facebook.com/v26.0"


def test_settings_aliases():
    # Test that MONGO_URI and MONGO_DB environment aliases work
    os.environ["MONGO_URI"] = "mongodb://testhost:27018"
    os.environ["MONGO_DB"] = "test_analytics_db"
    try:
        settings = Settings(_env_file=None)
        assert settings.mongodb_uri == "mongodb://testhost:27018"
        assert settings.mongodb_database == "test_analytics_db"
    finally:
        del os.environ["MONGO_URI"]
        del os.environ["MONGO_DB"]


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
