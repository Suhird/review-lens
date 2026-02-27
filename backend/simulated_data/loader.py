"""Loader for simulated review data (replaces scraping for demo products)."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from models import RawReview

logger = logging.getLogger(__name__)

_ITEMS_DIR = os.path.join(os.path.dirname(__file__), "items")
_cache: dict[str, dict] = {}


def _load_all() -> None:
    """Load all simulated item files into memory (called once)."""
    if _cache or not os.path.exists(_ITEMS_DIR):
        return
    for fname in os.listdir(_ITEMS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(_ITEMS_DIR, fname), "r") as f:
                    data = json.load(f)
                key = data.get("product_name", "").strip().lower()
                if key:
                    _cache[key] = data
            except Exception as e:
                logger.warning(f"Failed to load simulated data file {fname}: {e}")


def get_all_simulated_products() -> list[str]:
    """Return a sorted list of all simulated product names."""
    _load_all()
    return sorted(_cache.keys())


def get_simulated_reviews(query: str) -> Optional[dict]:
    """
    Return simulated review data for a query if a matching item exists.

    Returns a dict with:
        product_name: str
        image_url: str | None
        reviews: list[RawReview]

    Returns None if no match found (caller should proceed with real scraping).
    """
    _load_all()
    key = query.strip().lower()
    data = _cache.get(key)
    if data is None:
        return None

    raw_reviews: list[RawReview] = []
    for r in data.get("reviews", []):
        try:
            raw_reviews.append(RawReview.model_validate(r))
        except Exception as e:
            logger.debug(f"Skipping invalid simulated review: {e}")

    logger.info(f"Loaded {len(raw_reviews)} simulated reviews for '{query}'")
    return {
        "product_name": data.get("product_name", query),
        "image_url": data.get("image_url"),
        "reviews": raw_reviews,
    }
