"""Unit tests for sentiment analysis, keyword extraction, and trend calculation."""

from backend.app.ml.sentiment import (
    clean_caption,
    extract_keywords,
    extract_hashtags_from_caption,
    calculate_trend_score,
)


def test_clean_caption():
    raw = "Check this out! https://example.com/test @someuser #AmazingDay 🔥✨"
    cleaned = clean_caption(raw)
    assert "https" not in cleaned
    assert "@someuser" not in cleaned
    assert "AmazingDay" in cleaned


def test_extract_hashtags_from_caption():
    text = "Great time at #TechSummit2025 loving #AI and #DataScience!"
    tags = extract_hashtags_from_caption(text)
    assert "techsummit2025" in tags
    assert "ai" in tags
    assert "datascience" in tags


def test_extract_keywords():
    text = "Machine learning algorithms and deep neural networks are transforming technology"
    keywords = extract_keywords(text, top_n=5)
    assert len(keywords) > 0
    # Stopwords like 'and', 'are' must not be in keywords
    assert "and" not in keywords
    assert "are" not in keywords


def test_calculate_trend_score():
    # Higher current count should increase score
    low_score = calculate_trend_score(current_count=10, previous_count=10, avg_sentiment=0.0)
    high_score = calculate_trend_score(current_count=100, previous_count=10, avg_sentiment=0.5)
    assert high_score > low_score
    assert low_score >= 0.0

    # Zero count should produce 0.0
    zero_score = calculate_trend_score(current_count=0, previous_count=5)
    assert zero_score == 0.0
