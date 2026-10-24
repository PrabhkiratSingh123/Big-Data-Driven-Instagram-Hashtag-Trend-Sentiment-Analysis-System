"""
SocialTrendML — Demo Data Service
Generates synthetic Instagram-like posts for offline demonstration.
All demo data is clearly labeled with is_demo=True.
"""

import re
import random
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


# Seed for reproducible demo data
random.seed(42)

DEMO_HASHTAGS = ["technology", "artificialintelligence", "datascience", "sports", "fitness", "travel"]

DEMO_CAPTIONS = {
    "positive": [
        "Absolutely loving this incredible day! The vibes are unmatched ✨🔥",
        "Best decision I ever made — feeling so grateful and blessed 🙏💫",
        "Life is so beautiful when you appreciate the little things 😊🌸",
        "Finally achieved my goal! Hard work really does pay off 💪🎉",
        "Such a wonderful experience — highly recommend to everyone! ⭐👏",
        "So proud of how far I've come this year! Keep going 💪🌟",
        "Dream big, work hard, stay focused — it's all paying off! 🚀",
        "Amazing results from our latest experiment in the lab today",
        "This new framework makes development so much easier and faster",
        "Incredible breakthrough in AI research published today",
        "Great workout session this morning feeling energized and strong",
        "Beautiful hiking trail with stunning views everywhere you look",
        "Winning streak continues our team is on fire this season",
        "Revolutionary new approach to data processing just launched",
        "Love how the tech community always supports each other",
    ],
    "negative": [
        "Really disappointed with how things turned out today 😔",
        "This was honestly a waste of time and money 👎",
        "Feeling overwhelmed and exhausted — need a break 😞",
        "The quality has really gone downhill lately. So frustrating 😤",
        "Worst experience ever. Completely overrated 😡",
        "Struggling with motivation lately — feeling stuck 😕",
        "Another injury sidelining our best player for weeks",
        "The model keeps overfitting no matter what we try",
        "Terrible lag and performance issues with the latest update",
        "Lost the match in the final minutes absolutely devastating",
    ],
    "neutral": [
        "Just another day in the neighborhood 📸",
        "Here's what I've been working on lately 🔨",
        "Quick update from today's session. More details coming soon 📋",
        "Coffee and emails kind of morning ☕💻",
        "Working on some new things — stay tuned for updates 🔔",
        "Checking out this new approach to the problem",
        "Today's training schedule looks straightforward",
        "Reviewing the latest research papers in the field",
        "Standard practice session getting ready for next week",
        "Setting up the development environment for the new project",
    ],
}

HASHTAG_POOLS = {
    "technology": ["tech", "coding", "programming", "innovation", "software", "startup", "cloud", "devops"],
    "artificialintelligence": ["AI", "machinelearning", "deeplearning", "neuralnetworks", "GPT", "LLM", "robotics"],
    "datascience": ["data", "analytics", "bigdata", "python", "statistics", "visualization", "pandas"],
    "sports": ["football", "basketball", "soccer", "fitness", "athlete", "championship", "training"],
    "fitness": ["gym", "workout", "health", "gains", "crossfit", "yoga", "running", "nutrition"],
    "travel": ["wanderlust", "adventure", "explore", "vacation", "nature", "photography", "landscape"],
}


def generate_demo_post(
    source_hashtag: Optional[str] = None,
    sentiment: Optional[str] = None,
    hours_ago: Optional[int] = None,
) -> dict:
    """
    Generate a single synthetic Instagram post.
    Clearly marked as demo data (is_demo=True).
    """
    if source_hashtag is None:
        source_hashtag = random.choice(DEMO_HASHTAGS)

    if sentiment is None:
        sentiment = random.choices(
            ["positive", "negative", "neutral"],
            weights=[50, 20, 30],
            k=1,
        )[0]

    caption = random.choice(DEMO_CAPTIONS[sentiment])

    # Add related hashtags to caption
    related = HASHTAG_POOLS.get(source_hashtag, ["trending", "viral"])
    num_tags = random.randint(2, 5)
    tags = random.sample(related, min(num_tags, len(related)))
    tags.insert(0, source_hashtag)
    hashtag_str = " ".join(f"#{t}" for t in tags)
    full_caption = f"{caption} {hashtag_str}"

    # Generate deterministic post ID
    post_id = hashlib.md5(f"demo_{uuid.uuid4().hex}".encode()).hexdigest()[:16]

    # Timestamp
    if hours_ago is None:
        hours_ago = random.randint(0, 168)  # within last week
    timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)

    return {
        "post_id": f"demo_{post_id}",
        "caption": full_caption,
        "media_type": random.choices(["IMAGE", "VIDEO", "CAROUSEL_ALBUM"], weights=[55, 30, 15], k=1)[0],
        "permalink": f"https://www.instagram.com/p/demo_{post_id[:10]}/",
        "timestamp": timestamp,
        "hashtags": [t.lower() for t in tags],
        "source_hashtag": source_hashtag,
        "likes_count": max(0, int(random.gauss(350, 180))),
        "comments_count": max(0, int(random.gauss(28, 15))),
        "collected_at": datetime.now(timezone.utc),
        "is_demo": True,
        "_ground_truth_sentiment": sentiment,  # for testing only
    }


def generate_demo_batch(
    count: int = 50,
    hashtags: Optional[list[str]] = None,
) -> list[dict]:
    """
    Generate a batch of demo posts distributed across hashtags.
    Each post is clearly labeled as demo data.
    """
    if hashtags is None:
        hashtags = DEMO_HASHTAGS

    posts = []
    for i in range(count):
        source = hashtags[i % len(hashtags)]
        hours_ago = random.randint(0, 168)
        posts.append(generate_demo_post(source_hashtag=source, hours_ago=hours_ago))

    return posts


def seed_demo_data(db_manager, count: int = 200) -> int:
    """
    Seed the database with demo data for offline demonstration.
    Returns the number of posts inserted.
    """
    from backend.app.ml.sentiment import get_sentiment_analyzer

    posts = generate_demo_batch(count=count)

    # Store posts
    stored = db_manager.upsert_posts(posts)

    # Run sentiment analysis
    try:
        analyzer = get_sentiment_analyzer()
        sentiments = analyzer.analyze_batch(posts)
        db_manager.upsert_sentiment_results(sentiments)
    except Exception as e:
        # If analyzer fails, use ground truth from demo data
        fallback_sentiments = []
        for post in posts:
            fallback_sentiments.append({
                "post_id": post["post_id"],
                "caption": post["caption"],
                "sentiment": post.get("_ground_truth_sentiment", "neutral"),
                "confidence": 0.85,
                "keywords": _extract_keywords_simple(post["caption"]),
                "source_hashtag": post.get("source_hashtag", ""),
                "analyzed_at": datetime.now(timezone.utc),
                "model": "demo_ground_truth",
            })
        db_manager.upsert_sentiment_results(fallback_sentiments)

    # Compute and store hashtag metrics
    _compute_demo_metrics(db_manager, posts)

    # Create a collection run record
    run_id = db_manager.create_collection_run(DEMO_HASHTAGS, is_demo=True)
    db_manager.complete_collection_run(run_id, stored, "completed")

    return stored


def _compute_demo_metrics(db_manager, posts: list[dict]):
    """Compute hashtag metrics from demo posts."""
    from backend.app.ml.sentiment import calculate_trend_score
    from collections import Counter

    hashtag_posts: dict[str, list[dict]] = {}
    for p in posts:
        h = p.get("source_hashtag", "unknown")
        hashtag_posts.setdefault(h, []).append(p)

    metrics = []
    for hashtag, h_posts in hashtag_posts.items():
        sentiments = [p.get("_ground_truth_sentiment", "neutral") for p in h_posts]
        s_counts = Counter(sentiments)
        total = len(sentiments)

        keywords = []
        for p in h_posts:
            keywords.extend(_extract_keywords_simple(p.get("caption", "")))
        top_kw = [w for w, _ in Counter(keywords).most_common(10)]

        h_likes = sum(p.get("likes_count", 0) for p in h_posts)
        h_comments = sum(p.get("comments_count", 0) for p in h_posts)

        metrics.append({
            "hashtag": hashtag,
            "post_count": total,
            "avg_sentiment": (s_counts.get("positive", 0) - s_counts.get("negative", 0)) / max(total, 1),
            "positive_ratio": s_counts.get("positive", 0) / max(total, 1),
            "negative_ratio": s_counts.get("negative", 0) / max(total, 1),
            "neutral_ratio": s_counts.get("neutral", 0) / max(total, 1),
            "top_keywords": top_kw,
            "trend_score": calculate_trend_score(
                total, max(1, total - random.randint(0, 5)),
                avg_sentiment=(s_counts.get("positive", 0) - s_counts.get("negative", 0)) / max(total, 1),
            ),
            "avg_likes": round(h_likes / max(total, 1), 1),
            "avg_comments": round(h_comments / max(total, 1), 1),
            "engagement_rate": round((h_likes + h_comments) / max(total, 1), 2),
            "period_start": min(p["timestamp"] for p in h_posts),
            "period_end": max(p["timestamp"] for p in h_posts),
        })

    db_manager.upsert_hashtag_metrics(metrics)


def _extract_keywords_simple(text: str) -> list[str]:
    """Simple keyword extraction without heavy dependencies."""
    if not text:
        return []
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[^\w\s]", "", text.lower())
    stopwords = {"the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and", "or", "but", "not",
                 "with", "this", "that", "was", "are", "be", "has", "have", "had", "do", "just", "so", "my",
                 "i", "me", "we", "you", "he", "she", "they", "from", "up", "out", "all", "been"}
    return [w for w in text.split() if len(w) > 2 and w not in stopwords]
