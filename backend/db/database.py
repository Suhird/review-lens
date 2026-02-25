from __future__ import annotations

import logging
from typing import Optional

import asyncpg

from config import get_settings
from models import RawReview, FinalReport

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        # asyncpg uses postgresql:// not postgresql+asyncpg://
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def ping_postgres() -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"Postgres ping failed: {e}")
        return False


async def upsert_product(normalized_name: str, display_name: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO products (normalized_name, display_name)
            VALUES ($1, $2)
            ON CONFLICT (normalized_name) DO UPDATE SET display_name = $2
            RETURNING id::text
            """,
            normalized_name,
            display_name,
        )
        return row["id"]


async def store_reviews(product_id: str, reviews: list[RawReview]) -> None:
    if not reviews:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        for r in reviews:
            try:
                await conn.execute(
                    """
                    INSERT INTO reviews (
                        id, product_id, source, text, rating, review_date,
                        verified_purchase, helpful_votes, reviewer_id, fake_score
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (id) DO UPDATE
                    SET fake_score = $10
                    """,
                    r.id,
                    product_id,
                    r.source,
                    r.text,
                    r.rating,
                    r.date,
                    r.verified_purchase,
                    r.helpful_votes,
                    r.reviewer_id,
                    r.fake_score,
                )
            except Exception as e:
                logger.debug(f"Error storing review {r.id}: {e}")


async def store_report(product_id: str, report: FinalReport) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reports (product_id, report_json)
            VALUES ($1, $2::jsonb)
            """,
            product_id,
            report.model_dump_json(),
        )

async def get_report(normalized_name: str) -> Optional[FinalReport]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.report_json
            FROM reports r
            JOIN products p ON r.product_id = p.id
            WHERE p.normalized_name = $1
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            normalized_name,
        )
        if row:
            import json
            return FinalReport.model_validate(json.loads(row["report_json"]))
        return None
