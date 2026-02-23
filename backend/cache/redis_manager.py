from __future__ import annotations

import json
import logging
import re
from typing import Optional

import redis.asyncio as aioredis

from models import FinalReport, RawReview
from config import get_settings

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 hours


def normalize_name(name: str) -> str:
    """Lowercase, strip special chars, collapse whitespace."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name


def _report_cache_key(name: str) -> str:
    return f"reviewlens:{normalize_name(name)}"


def _reviews_cache_key(name: str) -> str:
    return f"reviews:{normalize_name(name)}"


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def _get_redis_client() -> aioredis.Redis:
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_cached_report(name: str) -> Optional[FinalReport]:
    async with _get_redis_client() as client:
        try:
            key = _report_cache_key(name)
            data = await client.get(key)
            if data:
                return FinalReport.model_validate_json(data)
        except Exception as e:
            logger.warning(f"Redis get_cached_report failed: {e}")
    return None


async def cache_report(name: str, report: FinalReport) -> None:
    async with _get_redis_client() as client:
        try:
            key = _report_cache_key(name)
            await client.setex(key, CACHE_TTL, report.model_dump_json())
        except Exception as e:
            logger.warning(f"Redis cache_report failed: {e}")


async def get_cached_reviews(name: str) -> Optional[list[RawReview]]:
    async with _get_redis_client() as client:
        try:
            key = _reviews_cache_key(name)
            data = await client.get(key)
            if data:
                raw = json.loads(data)
                return [RawReview.model_validate(r) for r in raw]
        except Exception as e:
            logger.warning(f"Redis get_cached_reviews failed: {e}")
    return None


async def cache_reviews(name: str, reviews: list[RawReview]) -> None:
    async with _get_redis_client() as client:
        try:
            key = _reviews_cache_key(name)
            data = json.dumps([r.model_dump(mode="json") for r in reviews])
            await client.setex(key, CACHE_TTL, data)
        except Exception as e:
            logger.warning(f"Redis cache_reviews failed: {e}")


async def get_job_data(job_id: str) -> Optional[dict]:
    async with _get_redis_client() as client:
        try:
            key = _job_key(job_id)
            data = await client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get_job_data failed: {e}")
    return None


async def set_job_data(job_id: str, data: dict, ttl: int = CACHE_TTL) -> None:
    async with _get_redis_client() as client:
        try:
            key = _job_key(job_id)
            await client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.warning(f"Redis set_job_data failed: {e}")


async def append_job_progress(job_id: str, message: str) -> None:
    job = await get_job_data(job_id)
    if job is None:
        job = {"status": "running", "progress": [], "errors": [], "report": None}
    job["progress"].append(message)
    await set_job_data(job_id, job)


async def ping_redis() -> bool:
    async with _get_redis_client() as client:
        try:
            return await client.ping()
        except Exception:
            return False
