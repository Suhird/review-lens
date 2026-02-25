from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Optional

import httpx

from models import RawReview
from config import get_settings

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

VIDEO_PHRASES = [
    "great video", "love your videos", "new subscriber", "thanks for sharing",
    "great review", "good review", "nice video", "subbed", "thanks for the review",
    "awesome review", "informative video", "helpful video"
]


def _make_review_id(comment_id: str) -> str:
    return hashlib.md5(f"youtube:{comment_id}".encode()).hexdigest()


async def scrape_youtube(query: str) -> list[RawReview]:
    settings = get_settings()

    if not settings.youtube_api_key:
        logger.warning("YouTube API key not configured, skipping YouTube scraper")
        return []

    reviews: list[RawReview] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Search for review videos
        search_params = {
            "part": "snippet",
            "q": f"{query} review",
            "type": "video",
            "maxResults": 5,
            "order": "viewCount",
            "key": settings.youtube_api_key,
        }

        try:
            search_resp = await client.get(YOUTUBE_SEARCH_URL, params=search_params)
            search_resp.raise_for_status()
            search_data = search_resp.json()
        except Exception as e:
            logger.warning(f"YouTube search failed: {e}")
            return []

        video_ids: list[str] = []
        for item in search_data.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)

        if not video_ids:
            logger.warning("YouTube: no videos found")
            return []

        # Fetch comments for each video
        for video_id in video_ids:
            comment_params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 100,
                "order": "relevance",
                "key": settings.youtube_api_key,
            }

            try:
                comments_resp = await client.get(YOUTUBE_COMMENTS_URL, params=comment_params)
                comments_resp.raise_for_status()
                comments_data = comments_resp.json()
            except Exception as e:
                logger.warning(f"YouTube comments fetch failed for {video_id}: {e}")
                continue

            for item in comments_data.get("items", []):
                try:
                    snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    text: str = snippet.get("textDisplay", "")

                    if len(text.strip()) < 50:
                        continue

                    text_lower = text.lower()
                    if any(phrase in text_lower for phrase in VIDEO_PHRASES):
                        continue

                    comment_id: str = item.get("id", "")
                    author: Optional[str] = snippet.get("authorDisplayName")
                    like_count: int = int(snippet.get("likeCount", 0))
                    published_at: Optional[str] = snippet.get("publishedAt")

                    review_date: Optional[datetime] = None
                    if published_at:
                        try:
                            review_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        except ValueError:
                            pass

                    review_id = _make_review_id(comment_id or text)
                    reviews.append(
                        RawReview(
                            id=review_id,
                            source="youtube",
                            text=text[:2000],
                            rating=None,
                            date=review_date,
                            verified_purchase=False,
                            helpful_votes=like_count,
                            reviewer_id=author,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Error parsing YouTube comment: {e}")
                    continue

    logger.info(f"YouTube scraper collected {len(reviews)} reviews")
    return reviews
