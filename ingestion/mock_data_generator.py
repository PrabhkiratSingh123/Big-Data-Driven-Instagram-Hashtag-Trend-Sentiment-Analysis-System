"""
Mock Instagram Data Generator
Generates realistic Instagram-like post data for development and testing.
Produces varied captions with sentiment-bearing text, realistic hashtag
distributions, and engagement metrics following power-law distributions.
"""

import random
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from faker import Faker

fake = Faker()
Faker.seed(42)

# =====================================================================
# Data Pools — curated for realistic, sentiment-rich content
# =====================================================================

HASHTAG_POOLS = {
    "trending": [
        "viral", "trending", "fyp", "explore", "reels",
        "instagood", "photooftheday", "instadaily", "instalike", "followme",
        "tbt", "picoftheday", "bestoftheday", "instamood", "nofilter",
    ],
    "lifestyle": [
        "lifestyle", "fashion", "ootd", "style", "beauty",
        "selfie", "makeup", "skincare", "wellness", "mindfulness",
        "selfcare", "positivevibes", "motivation", "luxury", "goals",
    ],
    "tech": [
        "tech", "coding", "programming", "AI", "machinelearning",
        "datascience", "python", "javascript", "startup", "innovation",
        "blockchain", "cybersecurity", "cloud", "devops", "opensource",
    ],
    "food": [
        "foodie", "foodporn", "instafood", "yummy", "delicious",
        "cooking", "recipe", "healthyfood", "vegan", "brunch",
        "coffee", "dessert", "homemade", "foodphotography", "chef",
    ],
    "travel": [
        "travel", "wanderlust", "adventure", "explore", "vacation",
        "travelgram", "travelphotography", "nature", "landscape", "sunset",
        "beach", "mountains", "roadtrip", "backpacking", "paradise",
    ],
    "fitness": [
        "fitness", "gym", "workout", "fitnessmotivation", "bodybuilding",
        "crossfit", "yoga", "running", "healthylifestyle", "fitfam",
        "gains", "personaltrainer", "exercise", "strength", "cardio",
    ],
    "music": [
        "music", "newmusic", "hiphop", "rap", "singer",
        "producer", "dj", "concert", "livemusic", "spotify",
        "soundcloud", "beats", "guitar", "piano", "musician",
    ],
    "art": [
        "art", "artist", "digitalart", "painting", "drawing",
        "illustration", "design", "creative", "artwork", "sketch",
        "photography", "portrait", "abstract", "gallery", "contemporaryart",
    ],
}

POSITIVE_CAPTIONS = [
    "Absolutely loving this incredible day! The vibes are unmatched ✨🔥",
    "Best decision I ever made — feeling so grateful and blessed 🙏💫",
    "Can't stop smiling! Life is so beautiful when you appreciate the little things 😊🌸",
    "This view just took my breath away! Nature is truly amazing 🏔️🌅",
    "Finally achieved my goal! Hard work really does pay off 💪🎉",
    "Surrounded by the most amazing people — thankful beyond words 💕",
    "Woke up feeling inspired and ready to conquer the world 🌍✨",
    "This made my entire week! So happy right now 😍🎊",
    "Living my best life and I wouldn't change a thing 🥂💃",
    "Such a wonderful experience — highly recommend to everyone! ⭐👏",
    "New personal record! Progress over perfection every single day 🏆",
    "The sunset tonight was absolutely magical — pure bliss 🌇💛",
    "So proud of how far I've come this year! Keep going 💪🌟",
    "This place is everything I dreamed of and more! Paradise found 🏝️😍",
    "Celebrating small wins because they lead to big victories 🎯🎊",
    "My heart is so full right now — grateful for every moment 💖",
    "Dream big, work hard, stay focused — it's all paying off! 🚀",
    "Incredible energy at this event! What an unforgettable night 🎶🔥",
    "Sometimes you just have to stop and appreciate how far you've come 🙌",
    "Found my happy place! Never want to leave here 🌺😌",
]

NEGATIVE_CAPTIONS = [
    "Really disappointed with how things turned out today 😔",
    "This was honestly a waste of time and money — would not recommend 👎",
    "Feeling overwhelmed and exhausted — need a break from everything 😞",
    "The quality has really gone downhill lately. So frustrating 😤",
    "Can't believe this happened again. When will things change? 💔",
    "Having one of those terrible days where nothing goes right 😢",
    "So tired of the fake positivity — let's be real for once 🙄",
    "Worst experience ever. Completely overrated and overpriced 😡",
    "Struggling with motivation lately — feeling stuck and lost 😕",
    "The traffic and crowds ruined what should have been a good day 😩",
    "Another broken promise. Trust is so hard to rebuild 💔",
    "This product completely failed after just one week of use 👎😤",
    "Missing how things used to be — change isn't always good 😔",
    "Terrible customer service experience — never going back there 😡",
    "Feeling so burnt out — when does the grind actually end? 😞",
]

NEUTRAL_CAPTIONS = [
    "Just another day in the neighborhood 📸",
    "New post — thoughts? Let me know in the comments below 👇",
    "Here's what I've been working on lately — work in progress 🔨",
    "Quick update from today's session. More details coming soon 📋",
    "Monday vibes. Back to the routine after the weekend ☕",
    "Trying something different today — we'll see how it goes 🤔",
    "Behind the scenes look at the process — not as glamorous as it seems 😅",
    "Just sharing some photos from the other day. Nothing special 📷",
    "Working on some new things — stay tuned for updates 🔔",
    "Coffee and emails kind of morning. The usual grind ☕💻",
    "Checking out this new place downtown — first impressions so far 🏙️",
    "Documenting the journey, one post at a time 📝",
    "Interesting perspective on things — what do you all think? 🤷",
    "Quick recap of the week — some good, some bad, mostly average 📊",
    "Just passing through — caught this random scene on my way 🚶",
]

MEDIA_TYPES = ["IMAGE", "VIDEO", "CAROUSEL_ALBUM"]
MEDIA_TYPE_WEIGHTS = [0.55, 0.30, 0.15]


def _generate_username() -> str:
    """Generate a realistic Instagram-style username."""
    patterns = [
        lambda: f"{fake.first_name().lower()}_{fake.last_name().lower()}",
        lambda: f"{fake.first_name().lower()}{random.randint(10, 999)}",
        lambda: f"the.{fake.word()}.{fake.word()}",
        lambda: f"{fake.word()}_{fake.word()}_official",
        lambda: f"{fake.first_name().lower()}.{fake.last_name().lower()[:3]}",
        lambda: f"x_{fake.word()}{random.randint(1, 99)}x",
        lambda: f"{fake.word()}{fake.word()}{random.randint(0, 9)}",
    ]
    return random.choice(patterns)()


def _generate_hashtags(category: Optional[str] = None, count: int = None) -> list[str]:
    """Generate a realistic set of hashtags mixing categories."""
    if count is None:
        count = random.choices(
            range(1, 12),
            weights=[3, 5, 8, 10, 12, 10, 8, 6, 4, 2, 1],
            k=1,
        )[0]

    # Pick a primary category
    if category is None:
        category = random.choice(list(HASHTAG_POOLS.keys()))

    primary_pool = HASHTAG_POOLS[category]
    trending_pool = HASHTAG_POOLS["trending"]

    hashtags = set()

    # 40-60% from primary category
    primary_count = max(1, int(count * random.uniform(0.4, 0.6)))
    hashtags.update(random.sample(primary_pool, min(primary_count, len(primary_pool))))

    # 20-30% from trending
    trending_count = max(1, int(count * random.uniform(0.2, 0.3)))
    hashtags.update(
        random.sample(trending_pool, min(trending_count, len(trending_pool)))
    )

    # Fill remaining from random categories
    while len(hashtags) < count:
        random_cat = random.choice(list(HASHTAG_POOLS.keys()))
        random_tag = random.choice(HASHTAG_POOLS[random_cat])
        hashtags.add(random_tag)

    return [f"#{tag}" for tag in list(hashtags)[:count]]


def _generate_engagement() -> tuple[int, int]:
    """
    Generate realistic engagement metrics following a power-law distribution.
    Most posts get moderate engagement, few go viral.
    """
    # Power-law-ish distribution for likes
    tier = random.choices(
        ["low", "medium", "high", "viral"],
        weights=[40, 35, 20, 5],
        k=1,
    )[0]

    if tier == "low":
        likes = random.randint(5, 100)
    elif tier == "medium":
        likes = random.randint(100, 1000)
    elif tier == "high":
        likes = random.randint(1000, 10000)
    else:  # viral
        likes = random.randint(10000, 500000)

    # Comments are typically 1-5% of likes
    comment_ratio = random.uniform(0.01, 0.06)
    comments = max(0, int(likes * comment_ratio + random.randint(0, 5)))

    return likes, comments


def generate_post(
    sentiment: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    Generate a single realistic Instagram post.

    Args:
        sentiment: Force a specific sentiment ('positive', 'negative', 'neutral').
                   If None, randomly selected with weighted probabilities.
        category: Force a specific hashtag category. If None, randomly selected.

    Returns:
        Dictionary representing an Instagram post.
    """
    # Select sentiment with realistic distribution
    if sentiment is None:
        sentiment = random.choices(
            ["positive", "negative", "neutral"],
            weights=[50, 20, 30],
            k=1,
        )[0]

    # Select caption based on sentiment
    caption_pools = {
        "positive": POSITIVE_CAPTIONS,
        "negative": NEGATIVE_CAPTIONS,
        "neutral": NEUTRAL_CAPTIONS,
    }
    caption = random.choice(caption_pools[sentiment])

    # Generate components
    hashtags = _generate_hashtags(category=category)
    likes, comments = _generate_engagement()
    media_type = random.choices(MEDIA_TYPES, weights=MEDIA_TYPE_WEIGHTS, k=1)[0]

    # Generate a deterministic but unique post_id
    post_id = hashlib.md5(
        f"{uuid.uuid4().hex}_{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    # Timestamp within the last few hours (simulating near-real-time)
    time_offset = random.randint(0, 7200)  # 0 to 2 hours ago
    timestamp = datetime.now(timezone.utc) - timedelta(seconds=time_offset)

    return {
        "post_id": post_id,
        "username": _generate_username(),
        "caption": f"{caption} {' '.join(hashtags)}",
        "hashtags": hashtags,
        "timestamp": timestamp.isoformat(),
        "media_type": media_type,
        "likes_count": likes,
        "comments_count": comments,
        "media_url": f"https://scontent.cdninstagram.com/v/t51.2885-15/{post_id}.jpg",
        "_sentiment_label": sentiment,  # ground truth for training; prefixed to distinguish
    }


def generate_batch(
    batch_size: int = 50,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Generate a batch of Instagram posts.

    Args:
        batch_size: Number of posts to generate.
        category: Optional category focus for this batch.

    Returns:
        List of post dictionaries.
    """
    posts = []
    for _ in range(batch_size):
        # Occasionally generate themed batches around a category
        post_category = category
        if post_category is None and random.random() < 0.3:
            post_category = random.choice(list(HASHTAG_POOLS.keys()))

        posts.append(generate_post(category=post_category))

    return posts


# Allow running standalone for testing
if __name__ == "__main__":
    import json

    print("Generating sample batch of 5 posts:\n")
    sample = generate_batch(batch_size=5)
    for i, post in enumerate(sample, 1):
        print(f"--- Post {i} ---")
        print(json.dumps(post, indent=2, default=str))
        print()
