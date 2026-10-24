"""Integration tests for FastAPI endpoints."""

import pytest
import mongomock
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.database.mongodb import MongoDBManager
import backend.app.database.mongodb as mongodb_mod


@pytest.fixture
def client():
    # Setup mock database instance
    mock_mgr = MongoDBManager(uri="mongodb://localhost:27017", database="test_db")
    mock_mgr._client = mongomock.MongoClient()
    mock_mgr._db = mock_mgr._client["test_db"]
    mongodb_mod._db_instance = mock_mgr

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    mongodb_mod._db_instance = None


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "uptime_seconds" in data


def test_hashtag_search_endpoint(client):
    response = client.get("/api/hashtags/search?q=technology")
    assert response.status_code == 200
    data = response.json()
    assert data["hashtag"] == "technology"
    assert "demo_mode" in data


def test_posts_endpoint(client):
    response = client.get("/api/posts?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "posts" in data
    assert "total" in data


def test_analytics_overview_endpoint(client):
    response = client.get("/api/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_posts" in data
    assert "tracked_hashtags" in data


def test_analytics_engagement_endpoint(client):
    response = client.get("/api/analytics/engagement?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "leaderboard" in data
    assert "summary" in data


def test_system_status_endpoint(client):
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert "api_status" in data
    assert "database_status" in data
