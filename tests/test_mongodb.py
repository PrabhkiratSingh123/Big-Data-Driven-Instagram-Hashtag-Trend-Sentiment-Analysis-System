"""Unit tests for MongoDBManager operations using mongomock."""

import pytest
import mongomock
from datetime import datetime, timezone
from backend.app.database.mongodb import MongoDBManager


@pytest.fixture
def mock_db():
    manager = MongoDBManager(uri="mongodb://localhost:27017", database="test_db")
    manager._client = mongomock.MongoClient()
    manager._db = manager._client["test_db"]
    return manager


def test_upsert_and_get_posts(mock_db):
    posts = [
        {
            "post_id": "test_1",
            "caption": "Exploring AI advances #technology",
            "source_hashtag": "technology",
            "likes_count": 120,
            "comments_count": 15,
            "timestamp": datetime.now(timezone.utc),
            "is_demo": True,
        },
        {
            "post_id": "test_2",
            "caption": "Latest data science tools #datascience",
            "source_hashtag": "datascience",
            "likes_count": 80,
            "comments_count": 8,
            "timestamp": datetime.now(timezone.utc),
            "is_demo": True,
        },
    ]

    stored = mock_db.upsert_posts(posts)
    assert stored == 2

    # Query all
    all_posts = mock_db.get_posts(limit=10)
    assert len(all_posts) == 2

    # Query filtered
    tech_posts = mock_db.get_posts(hashtag="technology")
    assert len(tech_posts) == 1
    assert tech_posts[0]["post_id"] == "test_1"

    # Count
    assert mock_db.get_post_count() == 2
    assert mock_db.get_post_count("technology") == 1

    # Unique hashtags
    tags = mock_db.get_unique_hashtags()
    assert "technology" in tags
    assert "datascience" in tags


def test_sentiment_upsert_and_dist(mock_db):
    sentiments = [
        {"post_id": "test_1", "sentiment": "positive", "confidence": 0.9, "source_hashtag": "technology"},
        {"post_id": "test_2", "sentiment": "negative", "confidence": 0.75, "source_hashtag": "technology"},
        {"post_id": "test_3", "sentiment": "positive", "confidence": 0.85, "source_hashtag": "datascience"},
    ]
    mock_db.upsert_sentiment_results(sentiments)

    dist = mock_db.get_sentiment_distribution()
    assert dist.get("positive") == 2
    assert dist.get("negative") == 1


def test_collection_runs(mock_db):
    run_id = mock_db.create_collection_run(["tech", "ai"], is_demo=True)
    assert len(run_id) > 0

    mock_db.complete_collection_run(run_id, posts_collected=45, status="completed")
    latest = mock_db.get_latest_collection_run()
    assert latest is not None
    assert latest["run_id"] == run_id
    assert latest["posts_collected"] == 45
    assert latest["status"] == "completed"
