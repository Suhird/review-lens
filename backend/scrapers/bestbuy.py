from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
from datetime import datetime
from typing import Optional

import httpx
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser

from models import RawReview
from scrapers.amazon import USER_AGENTS, _random_delay

logger = logging.getLogger(__name__)

BB_UGC_API = "https://www.bestbuy.com/ugc/v2/reviews"


def _make_review_id(text: str, reviewer: Optional[str]) -> str:
    raw = f"bestbuy:{reviewer or ''}:{text[:100]}"
    return hashlib.md5(raw.encode()).hexdigest()


def _extract_sku_from_search_page(html: str, query: str) -> Optional[str]:
    """
    Extract the first relevant numeric skuId from Best Buy search results HTML.
    Finds the skuId that appears closest to a mention of the query keywords.
    """
    import re

    query_words = [w.lower() for w in query.split() if len(w) > 2]

    # Find all (position, skuId) tuples in the document
    sku_positions = [(m.start(), m.group(1)) for m in re.finditer(r'"skuId"\s*:\s*"?(\d{5,})"?', html)]
    if not sku_positions:
        return None

    # Find positions of query keyword mentions
    html_lower = html.lower()
    best_sku = None
    best_dist = float("inf")

    for keyword in query_words:
        pos = 0
        while True:
            idx = html_lower.find(keyword, pos)
            if idx == -1:
                break
            # Find closest skuId to this position
            for sku_pos, sku in sku_positions:
                dist = abs(sku_pos - idx)
                if dist < best_dist:
                    best_dist = dist
                    best_sku = sku
            pos = idx + 1

    return best_sku


def _extract_sku_from_url(url: str) -> Optional[str]:
    """Try to extract numeric SKU from a Best Buy URL."""
    # New format: /product/{name}/{id} where id may be alphanumeric
    # Old format: /site/{name}/{sku}.p?skuId={sku}
    sku_match = re.search(r"[?&]skuId=(\d+)", url)
    if sku_match:
        return sku_match.group(1)
    # Try last path segment if numeric
    last_segment = url.rstrip("/").split("/")[-1]
    if last_segment.isdigit():
        return last_segment
    return None


def _fetch_reviews_sync(sku: str, max_pages: int = 3) -> list[RawReview]:
    """Synchronous version of Best Buy UGC API fetch for use in non-async contexts."""
    reviews: list[RawReview] = []
    headers = {"Accept": "application/json", "User-Agent": random.choice(USER_AGENTS)}

    for page_num in range(1, max_pages + 1):
        params = {"page": page_num, "pageSize": 20, "productId": sku, "sort": "MOST_HELPFUL"}
        try:
            resp = requests.get(BB_UGC_API, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                break
            data = resp.json()
            items = data.get("reviews", [])
            if not items:
                break
            for item in items:
                text = item.get("reviewText", "") or item.get("text", "")
                if not text:
                    continue
                rating_val = item.get("rating")
                rating: Optional[float] = float(rating_val) if rating_val else None
                submitted = item.get("submissionTime") or item.get("reviewSubmissionTime")
                review_date: Optional[datetime] = None
                if submitted:
                    try:
                        review_date = datetime.fromisoformat(str(submitted).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass
                verified = bool(item.get("verifiedPurchase", False))
                helpful_votes = int(item.get("positiveFeedbackCount", 0) or 0)
                reviewer = item.get("userNickname") or item.get("authorId")
                review_id = _make_review_id(text, str(reviewer) if reviewer else None)
                reviews.append(RawReview(
                    id=review_id, source="bestbuy", text=text[:2000],
                    rating=rating, date=review_date, verified_purchase=verified,
                    helpful_votes=helpful_votes, reviewer_id=str(reviewer) if reviewer else None,
                ))
        except Exception as e:
            logger.warning(f"Best Buy UGC API sync page {page_num} failed: {e}")
            break
    return reviews


async def _fetch_reviews_via_api(sku: str, max_pages: int = 3) -> list[RawReview]:
    """Use Best Buy's UGC reviews API to fetch reviews."""
    reviews: list[RawReview] = []
    headers = {
        "Accept": "application/json",
        "User-Agent": random.choice(USER_AGENTS),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for page_num in range(1, max_pages + 1):
            params = {
                "page": page_num,
                "pageSize": 20,
                "productId": sku,
                "sort": "MOST_HELPFUL",
            }
            try:
                resp = await client.get(BB_UGC_API, params=params, headers=headers)
                if resp.status_code != 200:
                    break
                data = resp.json()
                items = data.get("reviews", [])
                if not items:
                    break

                for item in items:
                    text = item.get("reviewText", "") or item.get("text", "")
                    if not text:
                        continue
                    rating_val = item.get("rating")
                    rating: Optional[float] = float(rating_val) if rating_val else None

                    submitted = item.get("submissionTime") or item.get("reviewSubmissionTime")
                    review_date: Optional[datetime] = None
                    if submitted:
                        try:
                            review_date = datetime.fromisoformat(str(submitted).replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            pass

                    verified = bool(item.get("verifiedPurchase", False))
                    helpful_votes = int(item.get("positiveFeedbackCount", 0) or 0)
                    reviewer = item.get("userNickname") or item.get("authorId")

                    review_id = _make_review_id(text, str(reviewer) if reviewer else None)
                    reviews.append(RawReview(
                        id=review_id,
                        source="bestbuy",
                        text=text[:2000],
                        rating=rating,
                        date=review_date,
                        verified_purchase=verified,
                        helpful_votes=helpful_votes,
                        reviewer_id=str(reviewer) if reviewer else None,
                    ))
            except Exception as e:
                logger.warning(f"Best Buy UGC API page {page_num} failed: {e}")
                break

    return reviews


def _parse_reviews_from_soup(soup: BeautifulSoup) -> list[RawReview]:
    """Parse reviews from Best Buy HTML page."""
    reviews: list[RawReview] = []

    # Try multiple review container selectors
    review_items = (
        soup.select("li.ugc-review")
        or soup.select("div.ugc-review")
        or soup.select("li.review-item")
        or soup.select("[class*='ugc-review']")
    )

    for item in review_items:
        try:
            text_el = (
                item.select_one("p.pre-white-space")
                or item.select_one("[class*='review-body']")
                or item.select_one("[class*='ugc-body']")
                or item.select_one("p")
            )
            text = text_el.get_text(strip=True) if text_el else ""
            if len(text) < 20:
                continue

            rating: Optional[float] = None
            for r_sel in ["p.sr-only", "[class*='rating'] p", "[aria-label*='out of 5']", ".c-reviewer-info-rating"]:
                rating_el = item.select_one(r_sel)
                if rating_el:
                    try:
                        parts = rating_el.get_text(strip=True).split()
                        for part in parts:
                            val = float(part)
                            if 1.0 <= val <= 5.0:
                                rating = val
                                break
                    except (ValueError, IndexError):
                        pass
                if rating:
                    break

            date_el = item.select_one("time, [class*='review-date'], [class*='submission-date']")
            review_date: Optional[datetime] = None
            if date_el:
                dt_str = date_el.get("datetime") or date_el.get_text(strip=True)
                for fmt in [None, "%m/%d/%Y", "%B %d, %Y"]:
                    try:
                        if fmt is None:
                            review_date = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
                        else:
                            review_date = datetime.strptime(str(dt_str), fmt)
                        break
                    except (ValueError, TypeError):
                        pass

            verified_el = item.select_one("[class*='verified'], [class*='Verified']")
            verified = verified_el is not None

            reviewer_el = item.select_one("[class*='author'], [class*='reviewer'], [class*='nickname']")
            reviewer = reviewer_el.get_text(strip=True) if reviewer_el else None

            review_id = _make_review_id(text, reviewer)
            reviews.append(RawReview(
                id=review_id,
                source="bestbuy",
                text=text,
                rating=rating,
                date=review_date,
                verified_purchase=verified,
                helpful_votes=0,
                reviewer_id=reviewer,
            ))
        except Exception as e:
            logger.debug(f"Error parsing Best Buy review: {e}")
            continue

    return reviews


async def _scrape_with_playwright(query: str) -> list[RawReview]:
    reviews: list[RawReview] = []

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/Chicago",
        )
        await context.add_cookies([
            {"name": "intl_splash", "value": "false", "domain": ".bestbuy.com", "path": "/"},
            {"name": "locStoreId", "value": "281", "domain": ".bestbuy.com", "path": "/"},
            {"name": "GeoRedirectCount", "value": "1", "domain": ".bestbuy.com", "path": "/"},
        ])
        page: Page = await context.new_page()
        await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        try:
            search_url = f"https://www.bestbuy.com/site/searchpage.jsp?st={query.replace(' ', '+')}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(_random_delay())

            content = await page.content()
            soup = BeautifulSoup(content, "lxml")

            # Extract SKU directly from search results page HTML
            sku = _extract_sku_from_search_page(content, query)
            product_link: Optional[str] = None

            if not sku:
                # Fallback: get product link and extract SKU from its URL
                for sel in ["a.product-list-item-link", "h4.sku-title a", "h2.sku-title a"]:
                    for a in soup.select(sel):
                        href = a.get("href", "")
                        if href.startswith("https://www.bestbuy.com") or href.startswith("/"):
                            product_link = href if href.startswith("http") else "https://www.bestbuy.com" + href
                            sku = _extract_sku_from_url(product_link)
                            break
                    if sku or product_link:
                        break

            # If we don't have a product link yet but we have a SKU, we need the link for the fallback
            if sku and not product_link:
                for sel in ["a.product-list-item-link", "h4.sku-title a", "h2.sku-title a"]:
                    for a in soup.select(sel):
                        href = a.get("href", "")
                        if sku in href:
                            product_link = href if href.startswith("http") else "https://www.bestbuy.com" + href
                            break
                    if product_link:
                        break

            if sku:
                logger.info(f"Best Buy: using UGC API for SKU {sku}")
                api_reviews = await _fetch_reviews_via_api(sku, max_pages=3)
                if api_reviews:
                    return api_reviews
                logger.warning(f"Best Buy: UGC API returned no reviews for SKU {sku}")
            else:
                logger.warning("Best Buy: could not extract SKU from search results")
            
            # Robust Fallback: Navigate to the product page and scrape HTML
            if product_link:
                logger.info(f"Best Buy Playwright: Falling back to scraping product page HTML: {product_link}")
                await page.goto(product_link, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(_random_delay())
                
                prod_content = await page.content()
                prod_soup = BeautifulSoup(prod_content, "lxml")
                html_reviews = _parse_reviews_from_soup(prod_soup)
                
                if html_reviews:
                    logger.info(f"Best Buy Playwright: scraped {len(html_reviews)} reviews from HTML")
                    return html_reviews
                else:
                    logger.warning(f"Best Buy Playwright: HTML scraper found 0 reviews on {product_link}")
            else:
                logger.warning("Best Buy Playwright: Cannot try HTML fallback because no product link was found.")

        finally:
            await browser.close()

    return reviews


def _scrape_with_requests(query: str) -> list[RawReview]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    cookies = {"intl_splash": "false", "locStoreId": "281"}
    reviews: list[RawReview] = []

    try:
        search_url = f"https://www.bestbuy.com/site/searchpage.jsp?st={query.replace(' ', '+')}"
        resp = requests.get(search_url, headers=headers, cookies=cookies, timeout=20)
        soup = BeautifulSoup(resp.text, "lxml")

        product_link: Optional[str] = None
        for sel in ["a.product-list-item-link", "h4.sku-title a", "h2.sku-title a"]:
            for a in soup.select(sel):
                href = a.get("href", "")
                if href.startswith("https://www.bestbuy.com"):
                    product_link = href
                    break
                elif href.startswith("/"):
                    product_link = "https://www.bestbuy.com" + href
                    break
            if product_link:
                break

        if not product_link:
            logger.warning("Best Buy requests: no product link found")
            return reviews

        resp2 = requests.get(product_link, headers=headers, cookies=cookies, timeout=20)

        # Try to get SKU and use API
        sku = _extract_sku_from_url(product_link)
        if not sku:
            sku_match = re.search(r'"skuId"\s*:\s*"?(\d+)"?', resp2.text)
            if sku_match:
                sku = sku_match.group(1)

        if sku:
            # Sync version of API fetch for requests fallback context
            api_reviews = _fetch_reviews_sync(sku, max_pages=3)
            if api_reviews:
                return api_reviews

        soup2 = BeautifulSoup(resp2.text, "lxml")
        reviews = _parse_reviews_from_soup(soup2)

    except Exception as e:
        logger.warning(f"Best Buy requests fallback failed: {e}")

    return reviews


async def scrape_bestbuy(query: str) -> list[RawReview]:
    try:
        reviews = await _scrape_with_playwright(query)
        if reviews:
            logger.info(f"Best Buy (Playwright) collected {len(reviews)} reviews")
            return reviews
    except Exception as e:
        logger.warning(f"Best Buy Playwright scraper failed, trying fallback: {e}")

    reviews = _scrape_with_requests(query)
    logger.info(f"Best Buy (requests fallback) collected {len(reviews)} reviews")
    return reviews
