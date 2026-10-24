"""
SocialTrendML — Instagram Graph API Collector
Implements the official Instagram Hashtag Search workflow:
1. GET /{ig-user-id}/ig_hashtag_search → get hashtag ID
2. GET /{hashtag-id}/recent_media → get recent posts
3. GET /{hashtag-id}/top_media → get top posts (optional)

Handles rate limits, pagination, retries with exponential backoff,
and never logs access tokens.
"""

import re
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class InstagramCollector:
    """
    Collects Instagram hashtag data through the official Graph API.

    Rate Limits (per Instagram docs):
    - 200 calls per user per hour
    - 30 unique hashtag searches per 7-day rolling window
    """

    # Fields available from the hashtag recent_media edge
    MEDIA_FIELDS = "id,caption,media_type,permalink,timestamp,like_count,comments_count"

    def __init__(self):
        settings = get_settings()
        self._access_token = settings.meta_access_token
        self._user_id = settings.instagram_user_id
        self._base_url = settings.graph_api_base_url
        self._session = self._create_session()
        self._hashtag_cache: dict[str, str] = {}  # name → ID cache

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are available."""
        return bool(self._access_token and self._user_id)

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _make_request(self, url: str, params: dict, attempt: int = 1, max_attempts: int = 3) -> dict:
        """
        Make an authenticated Graph API request with exponential backoff.
        Never logs the access token.
        """
        if not self.is_configured:
            raise RuntimeError(
                "Instagram API not configured. Set META_ACCESS_TOKEN and "
                "INSTAGRAM_USER_ID in your .env file."
            )

        # Add auth — token is NEVER logged
        params["access_token"] = self._access_token

        try:
            response = self._session.get(url, params=params, timeout=30)

            # Handle rate limiting
            if response.status_code == 429:
                if attempt < max_attempts:
                    wait = min(60 * (2 ** (attempt - 1)), 300)  # exponential backoff, max 5 min
                    logger.warning(f"Rate limited (429). Waiting {wait}s before retry {attempt+1}/{max_attempts}")
                    time.sleep(wait)
                    return self._make_request(url, {k: v for k, v in params.items() if k != "access_token"}, attempt + 1, max_attempts)
                raise RuntimeError("Rate limit exceeded after maximum retries")

            # Handle permission / auth errors
            if response.status_code in (400, 401, 403):
                error_data = response.json().get("error", {})
                error_msg = error_data.get("message", "Unknown API error")
                error_code = error_data.get("code", "unknown")
                logger.error(f"API error {response.status_code} (code={error_code}): {error_msg}")
                raise RuntimeError(f"Instagram API error ({error_code}): {error_msg}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            if attempt < max_attempts:
                wait = 5 * attempt
                logger.warning(f"Request timeout. Retrying in {wait}s ({attempt+1}/{max_attempts})")
                time.sleep(wait)
                return self._make_request(url, {k: v for k, v in params.items() if k != "access_token"}, attempt + 1, max_attempts)
            raise RuntimeError("Request timed out after maximum retries")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise RuntimeError(f"Cannot connect to Instagram API: {e}")

    def search_hashtag(self, hashtag: str) -> Optional[str]:
        """
        Search for a hashtag ID using the ig_hashtag_search endpoint.

        Args:
            hashtag: Hashtag name without #

        Returns:
            The hashtag ID, or None if not found
        """
        # Check cache first
        clean = hashtag.strip().lower().lstrip("#")
        if clean in self._hashtag_cache:
            return self._hashtag_cache[clean]

        url = f"{self._base_url}/ig_hashtag_search"
        params = {"user_id": self._user_id, "q": clean}

        try:
            result = self._make_request(url, params)
            data = result.get("data", [])
            if data:
                hashtag_id = data[0]["id"]
                self._hashtag_cache[clean] = hashtag_id
                logger.info(f"Found hashtag '{clean}' → ID {hashtag_id}")
                return hashtag_id
            logger.warning(f"Hashtag '{clean}' not found in API response")
            return None
        except Exception as e:
            logger.error(f"Hashtag search failed for '{clean}': {e}")
            return None

    def get_recent_media(self, hashtag_id: str, limit: int = 50) -> list[dict]:
        """
        Get recent media for a hashtag ID.
        Handles pagination using the API's returned paging cursors.

        Args:
            hashtag_id: The hashtag ID from search_hashtag()
            limit: Maximum posts to return

        Returns:
            List of raw post dictionaries from the API
        """
        url = f"{self._base_url}/{hashtag_id}/recent_media"
        params = {
            "user_id": self._user_id,
            "fields": self.MEDIA_FIELDS,
        }

        all_posts = []
        try:
            result = self._make_request(url, params)
            all_posts.extend(result.get("data", []))

            # Handle pagination
            while len(all_posts) < limit:
                paging = result.get("paging", {})
                next_url = paging.get("next")
                if not next_url:
                    break

                # The next URL includes the access token, so we use it directly
                response = self._session.get(next_url, timeout=30)
                response.raise_for_status()
                result = response.json()
                all_posts.extend(result.get("data", []))

                # Rate limit courtesy delay
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to get recent media for {hashtag_id}: {e}")

        return all_posts[:limit]

    def get_top_media(self, hashtag_id: str) -> list[dict]:
        """Get top media for a hashtag ID (optional edge)."""
        url = f"{self._base_url}/{hashtag_id}/top_media"
        params = {
            "user_id": self._user_id,
            "fields": self.MEDIA_FIELDS,
        }

        try:
            result = self._make_request(url, params)
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Failed to get top media for {hashtag_id}: {e}")
            return []

    def collect_hashtag(self, hashtag: str, include_top: bool = False) -> list[dict]:
        """
        Full collection workflow for a single hashtag:
        1. Search for hashtag ID
        2. Get recent media
        3. Optionally get top media
        4. Normalize all posts

        Returns:
            List of normalized post dictionaries
        """
        clean = hashtag.strip().lower().lstrip("#")
        logger.info(f"Collecting posts for #{clean}...")

        hashtag_id = self.search_hashtag(clean)
        if not hashtag_id:
            logger.warning(f"Cannot find hashtag '{clean}', skipping")
            return []

        posts = self.get_recent_media(hashtag_id)
        if include_top:
            top_posts = self.get_top_media(hashtag_id)
            # Merge, avoiding duplicates by post ID
            seen_ids = {p["id"] for p in posts}
            for tp in top_posts:
                if tp["id"] not in seen_ids:
                    posts.append(tp)

        # Normalize
        normalized = []
        for raw in posts:
            normalized.append(self._normalize_post(raw, clean))

        logger.info(f"Collected {len(normalized)} posts for #{clean}")
        return normalized

    def collect_multiple_hashtags(self, hashtags: list[str]) -> list[dict]:
        """Collect posts for multiple hashtags with rate-limit courtesy delays."""
        all_posts = []
        for hashtag in hashtags:
            posts = self.collect_hashtag(hashtag)
            all_posts.extend(posts)
            # Courtesy delay between different hashtag queries
            if len(hashtags) > 1:
                time.sleep(2)

        logger.info(f"Total collected: {len(all_posts)} posts from {len(hashtags)} hashtags")
        return all_posts

    def _normalize_post(self, raw: dict, source_hashtag: str) -> dict:
        """
        Normalize a raw API response into our standard post format.
        Only includes fields actually returned by the API.
        Does NOT fabricate engagement counts.
        """
        caption = raw.get("caption", "") or ""
        timestamp_str = raw.get("timestamp", "")

        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            timestamp = datetime.now(timezone.utc)

        return {
            "post_id": raw.get("id", str(uuid.uuid4())),
            "caption": caption,
            "media_type": raw.get("media_type", "IMAGE"),
            "permalink": raw.get("permalink", ""),
            "timestamp": timestamp,
            "hashtags": self._extract_hashtags(caption),
            "source_hashtag": source_hashtag,
            "likes_count": int(raw.get("like_count") or 0),
            "comments_count": int(raw.get("comments_count") or 0),
            "collected_at": datetime.now(timezone.utc),
            "is_demo": False,
        }

    @staticmethod
    def _extract_hashtags(caption: str) -> list[str]:
        """Extract hashtags from caption text."""
        if not caption:
            return []
        return [tag.lower() for tag in re.findall(r"#(\w+)", caption)]
