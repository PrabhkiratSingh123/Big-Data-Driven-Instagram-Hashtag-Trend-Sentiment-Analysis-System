"""
Instagram Graph API Client (Placeholder)
Provides the same interface as mock_data_generator for future real API integration.
When Meta API credentials are configured, this module will replace the mock generator
with real Instagram hashtag search and recent media endpoints.
"""

import logging
import time
from typing import Optional

import requests

from config import (
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_APP_ID,
    INSTAGRAM_API_BASE_URL,
)

logger = logging.getLogger(__name__)


class InstagramAPIClient:
    """
    Client for the Meta Instagram Graph API.
    Uses /ig_hashtag_search and /{hashtag-id}/recent_media endpoints.

    NOTE: This is a placeholder implementation. Full integration requires:
    1. A Meta Developer App with Instagram Graph API permissions
    2. An approved Instagram Business or Creator account
    3. Valid long-lived access token

    Rate limits apply:
    - 200 calls per hour per user
    - 30 unique hashtags per 7-day rolling window
    """

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or INSTAGRAM_ACCESS_TOKEN
        self.base_url = INSTAGRAM_API_BASE_URL
        self.session = requests.Session()
        self._rate_limit_remaining = 200
        self._rate_limit_reset = 0

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.access_token)

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated API request with rate limit handling."""
        if not self.is_configured:
            raise RuntimeError(
                "Instagram API not configured. Set INSTAGRAM_ACCESS_TOKEN "
                "in your environment or .env file."
            )

        if params is None:
            params = {}
        params["access_token"] = self.access_token

        url = f"{self.base_url}/{endpoint}"

        try:
            # Check rate limits
            if self._rate_limit_remaining <= 1:
                wait_time = max(0, self._rate_limit_reset - time.time()) + 1
                logger.warning(
                    f"Rate limit approaching. Waiting {wait_time:.0f}s..."
                )
                time.sleep(wait_time)

            response = self.session.get(url, params=params, timeout=30)

            # Track rate limits from headers
            self._rate_limit_remaining = int(
                response.headers.get("x-app-usage", 200)
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logger.error("Rate limit exceeded. Backing off...")
                time.sleep(60)
                return self._make_request(endpoint, params)
            logger.error(f"API HTTP error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def search_hashtag(self, hashtag: str, user_id: str) -> Optional[str]:
        """
        Search for a hashtag ID.

        Args:
            hashtag: Hashtag name (without #)
            user_id: Instagram Business Account ID

        Returns:
            Hashtag ID or None
        """
        try:
            result = self._make_request(
                "ig_hashtag_search",
                params={"q": hashtag, "user_id": user_id},
            )
            data = result.get("data", [])
            if data:
                return data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Hashtag search failed for '{hashtag}': {e}")
            return None

    def get_recent_media(
        self,
        hashtag_id: str,
        user_id: str,
        fields: str = "id,caption,media_type,like_count,comments_count,timestamp,permalink",
        limit: int = 50,
    ) -> list[dict]:
        """
        Get recent media for a hashtag.

        Args:
            hashtag_id: The hashtag ID from search_hashtag()
            user_id: Instagram Business Account ID
            fields: Comma-separated list of fields to request
            limit: Max number of posts to return

        Returns:
            List of post dictionaries
        """
        try:
            result = self._make_request(
                f"{hashtag_id}/recent_media",
                params={
                    "user_id": user_id,
                    "fields": fields,
                    "limit": limit,
                },
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Failed to get recent media for hashtag {hashtag_id}: {e}")
            return []

    def fetch_posts_for_hashtags(
        self,
        hashtags: list[str],
        user_id: str,
        posts_per_hashtag: int = 25,
    ) -> list[dict]:
        """
        Fetch posts for multiple hashtags and normalize to our schema.

        Args:
            hashtags: List of hashtag names (without #)
            user_id: Instagram Business Account ID
            posts_per_hashtag: Number of posts to fetch per hashtag

        Returns:
            List of normalized post dictionaries matching mock_data_generator format
        """
        all_posts = []

        for hashtag in hashtags:
            logger.info(f"Fetching posts for #{hashtag}...")

            hashtag_id = self.search_hashtag(hashtag, user_id)
            if not hashtag_id:
                logger.warning(f"Hashtag '{hashtag}' not found, skipping")
                continue

            raw_posts = self.get_recent_media(
                hashtag_id, user_id, limit=posts_per_hashtag
            )

            for raw in raw_posts:
                normalized = {
                    "post_id": raw.get("id", ""),
                    "username": "unknown",  # Not available from hashtag search
                    "caption": raw.get("caption", ""),
                    "hashtags": self._extract_hashtags(raw.get("caption", "")),
                    "timestamp": raw.get("timestamp", ""),
                    "media_type": raw.get("media_type", "IMAGE"),
                    "likes_count": raw.get("like_count", 0),
                    "comments_count": raw.get("comments_count", 0),
                    "media_url": raw.get("permalink", ""),
                }
                all_posts.append(normalized)

            # Respect rate limits between hashtag queries
            time.sleep(2)

        logger.info(f"Fetched {len(all_posts)} total posts from {len(hashtags)} hashtags")
        return all_posts

    @staticmethod
    def _extract_hashtags(caption: str) -> list[str]:
        """Extract hashtags from a caption string."""
        import re
        return re.findall(r"#\w+", caption.lower())
