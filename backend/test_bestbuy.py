import asyncio
import logging
from scrapers.bestbuy import scrape_bestbuy

logging.basicConfig(level=logging.DEBUG)

async def main():
    try:
        reviews = await scrape_bestbuy("playstation 5 console")
        print(f"Got {len(reviews)} reviews")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
