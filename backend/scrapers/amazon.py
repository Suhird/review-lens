from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup

from models import RawReview

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 14; Mobile; rv:121.0) Gecko/121.0 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]


def _make_review_id(source: str, text: str, reviewer_id: Optional[str]) -> str:
    raw = f"{source}:{reviewer_id or ''}:{text[:100]}"
    return hashlib.md5(raw.encode()).hexdigest()


def _random_delay() -> float:
    return random.uniform(2.0, 4.0)


def _is_captcha_page(content: str) -> bool:
    indicators = [
        "robot check",
        "captcha",
        "enter the characters you see below",
        "sorry, we just need to make sure you",
    ]
    lower = content.lower()
    return any(ind in lower for ind in indicators)


def _is_signin_page(content: str) -> bool:
    # Only flag as sign-in wall if the main form elements are present, not just nav links
    indicators = ["ap_email", "ap_password", "sign in to continue shopping", "sign in to see your"]
    lower = content.lower()
    return any(ind in lower for ind in indicators)


def _parse_reviews_from_soup(soup: BeautifulSoup) -> list[RawReview]:
    """Extract reviews from a parsed Amazon reviews page."""
    reviews: list[RawReview] = []

    # Primary selector
    review_divs = soup.select("div[data-hook='review']")

    # Fallback selectors for different page layouts
    if not review_divs:
        review_divs = soup.select("div[id^='customer_review-']")
    if not review_divs:
        review_divs = soup.select("div.review")

    for div in review_divs:
        try:
            text_el = (
                div.select_one("span[data-hook='review-body'] span")
                or div.select_one("span[data-hook='review-body']")
                or div.select_one(".review-text-content span")
                or div.select_one(".review-text")
            )
            text = text_el.get_text(strip=True) if text_el else ""
            if len(text) < 10:
                continue

            # Rating
            rating: Optional[float] = None
            for rating_sel in [
                "i[data-hook='review-star-rating'] span",
                "i[data-hook='cmps-review-star-rating'] span",
                ".review-rating span",
                "span.a-icon-alt",
            ]:
                rating_el = div.select_one(rating_sel)
                if rating_el:
                    try:
                        rating = float(rating_el.get_text(strip=True).split(" ")[0].split("\xa0")[0])
                        if 1.0 <= rating <= 5.0:
                            break
                        rating = None
                    except ValueError:
                        pass

            # Date
            review_date: Optional[datetime] = None
            date_el = div.select_one("span[data-hook='review-date']")
            if date_el:
                date_text = date_el.get_text(strip=True)
                if "on " in date_text:
                    try:
                        date_str = date_text.split("on ")[-1]
                        review_date = datetime.strptime(date_str, "%B %d, %Y")
                    except ValueError:
                        pass

            # Verified purchase
            verified_el = div.select_one("span[data-hook='avp-badge'], span.a-color-state")
            verified = verified_el is not None and "verified" in (verified_el.get_text(strip=True) or "").lower()

            # Helpful votes
            helpful_votes = 0
            helpful_el = div.select_one("span[data-hook='helpful-vote-statement']")
            if helpful_el:
                try:
                    helpful_votes = int(
                        helpful_el.get_text(strip=True).split(" ")[0].replace(",", "").replace("One", "1")
                    )
                except ValueError:
                    pass

            # Reviewer
            reviewer_el = div.select_one("span.a-profile-name")
            reviewer_id = reviewer_el.get_text(strip=True) if reviewer_el else None

            review_id = _make_review_id("amazon", text, reviewer_id)
            reviews.append(
                RawReview(
                    id=review_id,
                    source="amazon",
                    text=text,
                    rating=rating,
                    date=review_date,
                    verified_purchase=verified,
                    helpful_votes=helpful_votes,
                    reviewer_id=reviewer_id,
                )
            )
        except Exception as e:
            logger.debug(f"Error parsing individual review: {e}")
            continue

    return reviews


async def _get_product_links(page: Page, query: str) -> list[str]:
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(_random_delay())

    content = await page.content()
    if _is_captcha_page(content):
        logger.warning("Amazon search returned CAPTCHA page")
        return []

    soup = BeautifulSoup(content, "lxml")
    links: list[str] = []
    seen_asins: set[str] = set()

    for a_tag in soup.select("a.a-link-normal.s-no-outline"):
        href = a_tag.get("href", "")
        if "/dp/" in href:
            asin = href.split("/dp/")[1].split("/")[0].split("?")[0]
            if asin and asin not in seen_asins:
                seen_asins.add(asin)
                links.append(f"https://www.amazon.com/dp/{asin}")
                if len(links) >= 3:
                    break

    return links


async def _navigate_to_product(page: Page, product_url: str) -> bool:
    """
    Navigate to a product page. Reviews are parsed directly from the product page HTML,
    avoiding the /product-reviews/ URL which requires sign-in for headless browsers.
    Returns True if the product page loaded successfully with review content.
    """
    await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(_random_delay())

    content = await page.content()

    if _is_captcha_page(content):
        logger.warning(f"Amazon returned CAPTCHA for {product_url}")
        return False
    if _is_signin_page(content):
        logger.warning(f"Amazon returned sign-in wall for {product_url}")
        return False

    return True


async def _scrape_reviews_for_product(page: Page, product_url: str) -> list[RawReview]:
    """
    Scrape reviews by loading the product page directly.
    Amazon embeds the first page of reviews in the product page HTML.
    We parse those and also try paginating through the reviews section.
    """
    reviews: list[RawReview] = []

    success = await _navigate_to_product(page, product_url)
    if not success:
        return reviews

    content = await page.content()
    soup = BeautifulSoup(content, "lxml")
    page_reviews = _parse_reviews_from_soup(soup)
    reviews.extend(page_reviews)
    logger.debug(f"Amazon product page: parsed {len(page_reviews)} reviews from {product_url}")

    # Try to paginate through reviews on the product page (Amazon loads more via JS)
    for page_num in range(2, 6):
        try:
            next_btn = page.locator("li.a-last:not(.a-disabled) a")
            if await next_btn.count() == 0:
                break
            await next_btn.first.click()
            await asyncio.sleep(_random_delay())
            content = await page.content()
            if _is_captcha_page(content) or _is_signin_page(content):
                break
            soup = BeautifulSoup(content, "lxml")
            new_reviews = _parse_reviews_from_soup(soup)
            if not new_reviews:
                break
            reviews.extend(new_reviews)
        except Exception:
            break

    return reviews


async def scrape_amazon(query: str) -> list[RawReview]:
    all_reviews: list[RawReview] = []

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )
        # Hide webdriver fingerprint to reduce bot detection
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()

        # Set extra headers to appear more like a real browser
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

        try:
            product_links = await _get_product_links(page, query)
            if not product_links:
                logger.warning("No Amazon product links found")
                return []

            logger.info(f"Amazon: found {len(product_links)} products to scrape")

            for link in product_links[:3]:
                try:
                    page_reviews = await _scrape_reviews_for_product(page, link)
                    all_reviews.extend(page_reviews)
                    logger.info(f"Amazon: {len(page_reviews)} reviews from {link}")
                    await asyncio.sleep(_random_delay())
                except Exception as e:
                    logger.warning(f"Error scraping Amazon product {link}: {e}")
                    continue

        finally:
            await browser.close()

    logger.info(f"Amazon scraper collected {len(all_reviews)} reviews total")
    return all_reviews
