from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Optional

from models import RawReview
from config import get_settings

logger = logging.getLogger(__name__)

SUBREDDITS = ["BuyItForLife", "gadgets", "tech", "hardware", "ProductReviews"]


def _make_review_id(text: str, author: Optional[str]) -> str:
    raw = f"reddit:{author or ''}:{text[:100]}"
    return hashlib.md5(raw.encode()).hexdigest()


async def scrape_reddit(query: str) -> list[RawReview]:
    settings = get_settings()

    if not settings.reddit_client_id or not settings.reddit_client_secret:
        logger.warning("Reddit credentials not configured, skipping Reddit scraper")
        return []

    import praw

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    reviews: list[RawReview] = []
    search_terms = [
        f"{query} review",
        f"{query} experience",
        f"{query} worth it",
    ]

    for subreddit_name in SUBREDDITS:
        for search_term in search_terms:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                posts = list(subreddit.search(search_term, limit=50, sort="relevance"))

                for post in posts[:50]:
                    # Add the post body as a review if it's substantive
                    if post.selftext and len(post.selftext.strip()) > 50:
                        review_id = _make_review_id(post.selftext, str(post.author))
                        # Normalize upvotes as helpful_votes
                        helpful_votes = max(0, post.score)
                        date = datetime.utcfromtimestamp(post.created_utc) if post.created_utc else None

                        reviews.append(
                            RawReview(
                                id=review_id,
                                source="reddit",
                                text=post.selftext[:2000],
                                rating=None,
                                date=date,
                                verified_purchase=False,
                                helpful_votes=helpful_votes,
                                reviewer_id=str(post.author) if post.author else None,
                            )
                        )

                    # Add top comments
                    post.comments.replace_more(limit=0)
                    for comment in post.comments[:10]:
                        if not hasattr(comment, "body"):
                            continue
                        if len(comment.body.strip()) < 50:
                            continue

                        comment_id = _make_review_id(comment.body, str(comment.author))
                        comment_date = datetime.utcfromtimestamp(comment.created_utc) if comment.created_utc else None
                        reviews.append(
                            RawReview(
                                id=comment_id,
                                source="reddit",
                                text=comment.body[:2000],
                                rating=None,
                                date=comment_date,
                                verified_purchase=False,
                                helpful_votes=max(0, comment.score),
                                reviewer_id=str(comment.author) if comment.author else None,
                            )
                        )

            except Exception as e:
                logger.warning(f"Reddit scraper error for r/{subreddit_name} '{search_term}': {e}")
                continue

    # Deduplicate by id
    seen: set[str] = set()
    unique_reviews: list[RawReview] = []
    for r in reviews:
        if r.id not in seen:
            seen.add(r.id)
            unique_reviews.append(r)

    logger.info(f"Reddit scraper collected {len(unique_reviews)} reviews")
    return unique_reviews
