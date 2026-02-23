"""
Standalone scraper test — runs all 4 scrapers against a test query.
No Docker, no Ollama, no Postgres, no Redis needed.

Usage:
    python test_scrapers.py [query] [--debug]

Examples:
    python test_scrapers.py "Sony WH-1000XM5"
    python test_scrapers.py "Dyson V15" --debug
"""

import asyncio
import os
import sys
import time
import traceback
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"Loaded .env from {env_path}\n")
else:
    print("No .env file found — Reddit and YouTube will be skipped\n")

# Add backend to path so we can import scrapers directly
sys.path.insert(0, str(Path(__file__).parent / "backend"))

args = sys.argv[1:]
DEBUG = "--debug" in args
args = [a for a in args if a != "--debug"]
QUERY = args[0] if args else "Sony WH-1000XM5 headphones"
DEBUG_DIR = Path(__file__).parent / "scraper_debug"

if DEBUG:
    DEBUG_DIR.mkdir(exist_ok=True)
    print(f"Debug mode ON — HTML dumps will be saved to {DEBUG_DIR}/\n")

SEPARATOR = "─" * 60


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def result_summary(name: str, reviews: list, elapsed: float) -> None:
    if not reviews:
        print(f"  [RESULT] {name}: 0 reviews collected ({elapsed:.1f}s)")
        return

    rated = [r for r in reviews if r.rating is not None]
    avg_rating = sum(r.rating for r in rated) / len(rated) if rated else None
    verified = sum(1 for r in reviews if r.verified_purchase)

    print(f"  [RESULT] {name}: {len(reviews)} reviews in {elapsed:.1f}s")
    if avg_rating:
        print(f"    Avg rating:  {avg_rating:.2f}/5 (from {len(rated)} rated reviews)")
    if verified:
        print(f"    Verified:    {verified}")
    print(f"    Date range:  ", end="")
    dated = sorted([r for r in reviews if r.date], key=lambda r: r.date)
    if dated:
        print(f"{dated[0].date.strftime('%Y-%m')} → {dated[-1].date.strftime('%Y-%m')}")
    else:
        print("no dates")
    print()
    for i, r in enumerate(reviews[:3]):
        print(f"    [{i+1}] {r.source.upper()} | rating={r.rating} | verified={r.verified_purchase} | helpful={r.helpful_votes}")
        print(f"        {r.text[:120].strip()!r}")


async def test_amazon_debug(query: str) -> list:
    """Debug-mode Amazon test that shows page content."""
    import random
    from playwright.async_api import async_playwright
    from scrapers.amazon import USER_AGENTS, _random_delay, _is_captcha_page

    print("  Running in debug mode — navigating manually...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
        print(f"  Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        content = await page.content()
        title = await page.title()
        print(f"  Page title: {title!r}")
        print(f"  Content length: {len(content)} chars")
        print(f"  Is CAPTCHA: {_is_captcha_page(content)}")

        if DEBUG:
            dump = DEBUG_DIR / "amazon_search.html"
            dump.write_text(content, encoding="utf-8")
            print(f"  HTML saved to: {dump}")

        # Show what links were found
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "lxml")
        product_links = []
        for a in soup.select("a.a-link-normal.s-no-outline"):
            href = a.get("href", "")
            if "/dp/" in href:
                asin = href.split("/dp/")[1].split("/")[0].split("?")[0]
                product_links.append(f"https://www.amazon.com/dp/{asin}")

        print(f"  Product links found: {len(product_links)}")
        for lnk in product_links[:3]:
            print(f"    {lnk}")

        if not product_links:
            # Show first 10 links on page for diagnosis
            all_links = [(a.get("href",""), a.get_text(strip=True)[:40]) for a in soup.find_all("a", href=True)[:20]]
            print("  First 20 links on page:")
            for href, text in all_links:
                print(f"    {text!r:40s} → {href[:80]}")

        await browser.close()

    return []


async def test_amazon(query: str):
    section("Amazon Scraper (Playwright)")
    print(f"  Query: {query!r}")

    if DEBUG:
        try:
            return await test_amazon_debug(query)
        except Exception as e:
            print(f"  [ERROR] {e}")
            traceback.print_exc()
            return []

    print("  Scraping... (may take 20-60s, Amazon often blocks)")

    try:
        from scrapers.amazon import scrape_amazon
        t0 = time.time()
        reviews = await scrape_amazon(query)
        elapsed = time.time() - t0
        result_summary("Amazon", reviews, elapsed)
        return reviews
    except Exception as e:
        print(f"  [ERROR] Amazon scraper failed: {e}")
        if DEBUG:
            traceback.print_exc()
        return []


async def test_reddit(query: str):
    section("Reddit Scraper (PRAW)")
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")

    if not client_id or client_id == "your_reddit_client_id":
        print("  [SKIP] REDDIT_CLIENT_ID not set in .env")
        print("  To enable: edit .env and add your Reddit API credentials")
        print("  Get them at: https://www.reddit.com/prefs/apps")
        return []

    print(f"  Query: {query!r}")
    print(f"  Client ID: {client_id[:6]}...")
    print("  Scraping...")

    try:
        from scrapers.reddit import scrape_reddit
        t0 = time.time()
        reviews = await scrape_reddit(query)
        elapsed = time.time() - t0
        result_summary("Reddit", reviews, elapsed)
        return reviews
    except Exception as e:
        print(f"  [ERROR] Reddit scraper failed: {e}")
        if DEBUG:
            traceback.print_exc()
        return []


async def test_bestbuy_debug(query: str) -> list:
    """Debug-mode Best Buy test that shows page content."""
    import random
    from playwright.async_api import async_playwright
    from scrapers.amazon import USER_AGENTS

    print("  Running in debug mode — navigating manually...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        url = f"https://www.bestbuy.com/site/searchpage.jsp?st={query.replace(' ', '+')}"
        print(f"  Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        content = await page.content()
        title = await page.title()
        print(f"  Page title: {title!r}")
        print(f"  Content length: {len(content)} chars")

        if DEBUG:
            dump = DEBUG_DIR / "bestbuy_search.html"
            dump.write_text(content, encoding="utf-8")
            print(f"  HTML saved to: {dump}")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "lxml")

        # Try various product link selectors
        selectors_to_try = [
            "h4.sku-title a",
            "a.image-link",
            "a[href*='/site/']",
            ".sku-item a",
            "div.shop-sku-list-item a",
        ]
        for sel in selectors_to_try:
            found = soup.select(sel)
            print(f"  Selector {sel!r}: {len(found)} matches")
            for a in found[:2]:
                print(f"    href={a.get('href','')[:80]!r}  text={a.get_text(strip=True)[:40]!r}")

        await browser.close()
    return []


async def test_bestbuy(query: str):
    section("Best Buy Scraper (Playwright + requests fallback)")
    print(f"  Query: {query!r}")

    if DEBUG:
        try:
            return await test_bestbuy_debug(query)
        except Exception as e:
            print(f"  [ERROR] {e}")
            traceback.print_exc()
            return []

    print("  Scraping... (may take 20-40s)")

    try:
        from scrapers.bestbuy import scrape_bestbuy
        t0 = time.time()
        reviews = await scrape_bestbuy(query)
        elapsed = time.time() - t0
        result_summary("Best Buy", reviews, elapsed)
        return reviews
    except Exception as e:
        print(f"  [ERROR] Best Buy scraper failed: {e}")
        if DEBUG:
            traceback.print_exc()
        return []


async def test_youtube(query: str):
    section("YouTube Scraper (Data API v3)")
    api_key = os.getenv("YOUTUBE_API_KEY", "")

    if not api_key or api_key == "your_youtube_api_key_optional":
        print("  [SKIP] YOUTUBE_API_KEY not set in .env")
        print("  To enable: add your YouTube Data API v3 key to .env")
        print("  Get it at: https://console.cloud.google.com (free)")
        return []

    print(f"  Query: {query!r}")
    print(f"  API Key: {api_key[:8]}...")
    print("  Scraping...")

    try:
        from scrapers.youtube import scrape_youtube
        t0 = time.time()
        reviews = await scrape_youtube(query)
        elapsed = time.time() - t0
        result_summary("YouTube", reviews, elapsed)
        return reviews
    except Exception as e:
        print(f"  [ERROR] YouTube scraper failed: {e}")
        if DEBUG:
            traceback.print_exc()
        return []


async def main():
    print("=" * 60)
    print("  ReviewLens — Scraper Test")
    print("=" * 60)
    print(f"  Query: {QUERY!r}")
    print(f"  Debug: {DEBUG}")
    print(f"  Running all 4 scrapers sequentially...")

    total_start = time.time()

    amazon_reviews  = await test_amazon(QUERY)
    reddit_reviews  = await test_reddit(QUERY)
    bestbuy_reviews = await test_bestbuy(QUERY)
    youtube_reviews = await test_youtube(QUERY)

    total_elapsed = time.time() - total_start
    all_reviews = amazon_reviews + reddit_reviews + bestbuy_reviews + youtube_reviews

    section("Summary")
    print(f"  Amazon:   {len(amazon_reviews):4d} reviews")
    print(f"  Reddit:   {len(reddit_reviews):4d} reviews")
    print(f"  Best Buy: {len(bestbuy_reviews):4d} reviews")
    print(f"  YouTube:  {len(youtube_reviews):4d} reviews")
    print(f"  {'─'*30}")
    print(f"  TOTAL:    {len(all_reviews):4d} reviews in {total_elapsed:.1f}s")

    if all_reviews:
        rated = [r for r in all_reviews if r.rating is not None]
        if rated:
            avg = sum(r.rating for r in rated) / len(rated)
            print(f"  Avg rating (rated only): {avg:.2f}/5")
        sources = {}
        for r in all_reviews:
            sources[r.source] = sources.get(r.source, 0) + 1
        print(f"  By source: {sources}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
