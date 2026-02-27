import hashlib
import logging
from datetime import datetime
from typing import Optional

import httpx

from config import get_settings
from models import RawReview

logger = logging.getLogger(__name__)

settings = get_settings()


def _make_review_id(text: str, source: str) -> str:
    raw = f"google:{source}:{text[:100]}"
    return hashlib.md5(raw.encode()).hexdigest()


async def scrape_google(query: str) -> list[RawReview]:
    """
    Search for reviews using Google Custom Search API.
    A Custom Search Engine (CX) must be configured to target specific sites like
    bestbuy.com, costco.com, and walmart.com.
    """
    if not settings.google_search_api_key or not settings.google_search_cx:
        logger.warning("Google Search API credentials missing, skipping Google scraper")
        return []

    reviews: list[RawReview] = []
    
    # We append "reviews" to the search query to bias the engine towards review pages
    search_query = f"{query} reviews"
    
    # We fetch 2 pages (20 results total) to avoid eating up the free quota of 100/day too fast.
    max_pages = 2
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for page_num in range(max_pages):
            start = page_num * 10 + 1
            params = {
                "key": settings.google_search_api_key,
                "cx": settings.google_search_cx,
                "q": search_query,
                "start": start,
            }
            try:
                url = "https://customsearch.googleapis.com/customsearch/v1"
                resp = await client.get(url, params=params)
                
                if resp.status_code != 200:
                    logger.warning(f"Google Search API failed with status {resp.status_code}: {resp.text}")
                    break
                    
                data = resp.json()
                items = data.get("items", [])
                
                if not items:
                    break
                
                for item in items:
                    link = item.get("link", "")
                    snippet = item.get("snippet", "")
                    
                    if not snippet:
                        continue
                        
                    # Extract source domain
                    source = "google"
                    if "costco.com" in link:
                        source = "costco"
                    elif "walmart.com" in link:
                        source = "walmart"
                    elif "bestbuy.com" in link:
                        source = "bestbuy"
                        
                    # Attempt to extract rating from pagemap schema if present
                    rating: Optional[float] = None
                    pagemap = item.get("pagemap", {})
                    
                    aggregaterating = pagemap.get("aggregaterating", [])
                    if aggregaterating:
                        rating_val = aggregaterating[0].get("ratingvalue")
                        if rating_val:
                            try:
                                rating = float(rating_val)
                            except ValueError:
                                pass
                    
                    review_schema = pagemap.get("review", [])
                    if not rating and review_schema:
                        rating_val = review_schema[0].get("ratingstars") or review_schema[0].get("reviewrating", {}).get("ratingvalue")
                        if rating_val:
                            try:
                                rating = float(rating_val)
                            except ValueError:
                                pass
                    
                    # Google Custom Search snippets usually trail off with "..."
                    # We will treat the snippet as the review text. 
                    # Dates are rarely well-structured in standard search snippets independently of pagemap schema.
                    review_id = _make_review_id(snippet, source)
                    
                    reviews.append(RawReview(
                        id=review_id,
                        source=source,
                        text=snippet,
                        rating=rating,
                        date=None, 
                        verified_purchase=False,
                        helpful_votes=0,
                        reviewer_id=None,
                    ))

            except Exception as e:
                logger.warning(f"Google Search API page {page_num + 1} failed: {e}")
                break

    return reviews
