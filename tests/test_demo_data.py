"""Unit tests for demo data generation service."""

from backend.app.services.demo_data import (
    generate_demo_post,
    generate_demo_batch,
    _extract_keywords_simple,
)


def test_generate_demo_post():
    post = generate_demo_post(source_hashtag="technology")
    assert post["is_demo"] is True
    assert post["source_hashtag"] == "technology"
    assert post["post_id"].startswith("demo_")
    assert isinstance(post["likes_count"], int)
    assert isinstance(post["comments_count"], int)
    assert post["likes_count"] >= 0
    assert post["comments_count"] >= 0
    assert len(post["hashtags"]) >= 1


def test_generate_demo_batch():
    batch = generate_demo_batch(count=30, hashtags=["tech", "fitness"])
    assert len(batch) == 30
    sources = {p["source_hashtag"] for p in batch}
    assert "tech" in sources
    assert "fitness" in sources


def test_extract_keywords_simple():
    text = "Awesome deep neural network for natural language processing"
    keywords = _extract_keywords_simple(text)
    assert "awesome" in keywords
    assert "neural" in keywords
    assert "the" not in keywords
