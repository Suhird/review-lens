from __future__ import annotations

import asyncio
import logging
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph import StateGraph, END

from models import (
    RawReview,
    ReviewAspect,
    FakeReviewReport,
    DriftReport,
    ReviewCluster,
    FinalReport,
)

logger = logging.getLogger(__name__)


def _last_non_none(a, b):
    """Reducer: keep the last non-None value (for parallel branches)."""
    return b if b is not None else a


class ReviewLensState(TypedDict):
    job_id: str
    query: str
    use_cache: bool
    enriched_queries: list[str]
    raw_reviews: list[RawReview]
    product_image: Annotated[Optional[str], _last_non_none]
    cleaned_reviews: list[RawReview]
    aspect_scores: list[ReviewAspect]
    fake_report: FakeReviewReport
    drift_report: DriftReport
    clusters: list[ReviewCluster]
    final_report: FinalReport
    errors: Annotated[list[str], operator.add]

async def _flush_progress(job_id: str, query: str, message=None, errors: list[str] | None = None):
    """Append a single progress message to the job in Redis (safe for parallel nodes)."""
    from cache.redis_manager import get_job_data, set_job_data
    job = await get_job_data(job_id) or {"status": "running", "progress": [], "errors": []}
    job["query"] = query
    if message is not None:
        job.setdefault("progress", []).append(message)
    if errors:
        existing = job.get("errors", [])
        for e in errors:
            if e not in existing:
                existing.append(e)
        job["errors"] = existing
    await set_job_data(job_id, job)



async def enrich_query_node(state: ReviewLensState) -> dict:
    from agents.synthesis_agent import enrich_query

    query = state["query"]
    new_errors: list[str] = []

    await _flush_progress(state["job_id"], query, {"task": "enrichment", "status": "running", "message": "Enriching query with LLM..."})
    try:
        enriched = await enrich_query(query)
    except Exception as e:
        logger.warning(f"Query enrichment failed: {e}")
        new_errors.append(f"Query enrichment failed: {e}")
        await _flush_progress(state["job_id"], query, {"task": "enrichment", "status": "complete", "message": "Query enrichment failed, using original query"}, new_errors)
        enriched = [query]
    else:
        await _flush_progress(state["job_id"], query, {"task": "enrichment", "status": "complete", "message": "Query enrichment complete"})

    # Return ONLY changed keys (no **state) — critical for parallel branch merge
    return {
        "enriched_queries": enriched,
        "errors": new_errors,
    }


async def scraper_node(state: ReviewLensState) -> dict:
    from scrapers.amazon import scrape_amazon
    from scrapers.reddit import scrape_reddit
    from scrapers.bestbuy import scrape_bestbuy
    from scrapers.youtube import scrape_youtube
    from cache.redis_manager import get_cached_reviews, cache_reviews, normalize_name
    from db.database import store_reviews, upsert_product

    query = state["query"]
    enriched = state.get("enriched_queries", [query])
    use_cache = state.get("use_cache", True)
    new_errors: list[str] = []
    all_reviews: list[RawReview] = []
    product_image: Optional[str] = None

    norm_query = normalize_name(query)

    if use_cache:
        cached = await get_cached_reviews(norm_query)
        if cached:
            await _flush_progress(state["job_id"], query, {"task": "scrape", "status": "complete", "message": f"Loaded {len(cached)} reviews from cache"})
            return {
                "raw_reviews": cached,
                "cleaned_reviews": cached,
                "errors": [],
            }

    await _flush_progress(state["job_id"], query, {"task": "scrape", "status": "running", "message": "Scraping reviews from all sources..."})

    try:
        term = enriched[0] if enriched else query
        logger.info(f"Scraping for term: {term}")

        scrapers = [
            scrape_amazon(term),
            scrape_bestbuy(term),
            scrape_reddit(term),
            scrape_youtube(term),
        ]
        results = await asyncio.gather(*scrapers, return_exceptions=True)

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Scraper error: {res}")
                new_errors.append(f"Scraper error: {str(res)}")
            elif isinstance(res, list):
                logger.info(f"Scraper {i}: returned {len(res)} reviews (list)")
                all_reviews.extend(res)
            elif isinstance(res, tuple):
                reviews, img = res
                logger.info(f"Scraper {i}: returned {len(reviews)} reviews, image={img is not None}")
                all_reviews.extend(reviews)
                if img and not product_image:
                    product_image = img

        if all_reviews:
            pid = await upsert_product(norm_query, query)
            await store_reviews(pid, all_reviews)
            await cache_reviews(norm_query, all_reviews)

    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        new_errors.append(f"Scraping framework error: {e}")

    logger.info(f"Scraper node: total={len(all_reviews)} reviews, product_image={'YES: ' + product_image[:80] if product_image else 'None'}")
    await _flush_progress(state["job_id"], query, {"task": "scrape", "status": "complete", "message": f"Total reviews collected: {len(all_reviews)}"}, new_errors)

    # Return ONLY changed keys (no **state) — critical for parallel branch merge
    result: dict = {
        "raw_reviews": all_reviews,
        "cleaned_reviews": all_reviews,
        "errors": new_errors,
    }
    if product_image:
        result["product_image"] = product_image
    return result


async def analysis_node(state: ReviewLensState) -> dict:
    from analysis.absa import run_absa
    from analysis.fake_detector import detect_fake_reviews
    from analysis.drift_detector import detect_drift
    from analysis.clusterer import cluster_reviews

    reviews = state.get("cleaned_reviews", [])
    query = state["query"]
    product_image = state.get("product_image")
    new_errors: list[str] = []

    if not reviews:
        empty_report = FinalReport(
            product_name=query,
            image_url=product_image,
            overall_score=0.0,
            total_reviews_analyzed=0,
            sources_used=[],
            sentiment_breakdown={"positive": 0, "neutral": 0, "negative": 0},
            aspect_scores=[],
            fake_report=FakeReviewReport(
                total_reviews=0, flagged_count=0, fake_percentage=0.0,
                flagged_ids=[], risk_level="low"
            ),
            drift_report=DriftReport(monthly_sentiment=[], change_points=[], trend="stable"),
            clusters=[],
            featured_reviews=[],
            executive_summary="No reviews found.",
            who_should_buy="",
            who_should_skip="",
            verdict="Insufficient data"
        )
        return {"final_report": empty_report, "errors": []}

    # ABSA
    await _flush_progress(state["job_id"], query, {"task": "analysis", "status": "running", "message": "Running aspect-based sentiment analysis..."})
    try:
        aspect_scores, reviews_with_fake = await run_absa(reviews)
    except Exception as e:
        logger.error(f"ABSA failed: {e}")
        new_errors.append(f"ABSA failed: {e}")
        aspect_scores = []
        reviews_with_fake = reviews

    # Fake detection
    await _flush_progress(state["job_id"], query, {"task": "analysis", "status": "running", "message": "Detecting fake reviews..."})
    try:
        fake_report, reviews_scored = detect_fake_reviews(reviews_with_fake)
    except Exception as e:
        logger.error(f"Fake detection failed: {e}")
        new_errors.append(f"Fake detection failed: {e}")
        fake_report = FakeReviewReport(
            total_reviews=len(reviews),
            flagged_count=0,
            fake_percentage=0.0,
            flagged_ids=[],
            risk_level="low",
        )
        reviews_scored = reviews

    # Drift detection
    await _flush_progress(state["job_id"], query, {"task": "analysis", "status": "running", "message": "Analyzing sentiment drift over time..."})
    try:
        drift_report = detect_drift(reviews_scored)
    except Exception as e:
        logger.error(f"Drift detection failed: {e}")
        new_errors.append(f"Drift detection failed: {e}")
        drift_report = DriftReport(monthly_sentiment=[], change_points=[], trend="stable")

    # Clustering
    await _flush_progress(state["job_id"], query, {"task": "analysis", "status": "running", "message": "Clustering reviews by theme..."})
    try:
        clusters = await cluster_reviews(reviews_scored)
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        new_errors.append(f"Clustering failed: {e}")
        clusters = []

    await _flush_progress(state["job_id"], query, {"task": "analysis", "status": "complete", "message": "Analysis complete"}, new_errors)

    return {
        "cleaned_reviews": reviews_scored,
        "aspect_scores": aspect_scores,
        "fake_report": fake_report,
        "drift_report": drift_report,
        "clusters": clusters,
        "errors": new_errors,
    }


async def synthesis_node(state: ReviewLensState) -> dict:
    from agents.synthesis_agent import synthesize_report

    new_errors: list[str] = []

    await _flush_progress(state["job_id"], state["query"], {"task": "synthesis", "status": "running", "message": "Synthesizing final report..."})
    try:
        final_report = await synthesize_report(state)
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        new_errors.append(f"Synthesis failed: {e}")
        reviews = state.get("cleaned_reviews", [])
        sources = list({r.source for r in reviews})
        final_report = FinalReport(
            product_name=state["query"],
            image_url=state.get("product_image"),
            overall_score=0.0,
            total_reviews_analyzed=len(reviews),
            sources_used=sources,
            sentiment_breakdown={},
            aspect_scores=state.get("aspect_scores", []),
            fake_report=state.get("fake_report", FakeReviewReport(
                total_reviews=0, flagged_count=0, fake_percentage=0.0,
                flagged_ids=[], risk_level="low"
            )),
            drift_report=state.get("drift_report", DriftReport(
                monthly_sentiment=[], change_points=[], trend="stable"
            )),
            clusters=state.get("clusters", []),
            featured_reviews=[],
            executive_summary="Report generation encountered errors.",
            who_should_buy="Unable to determine.",
            who_should_skip="Unable to determine.",
            verdict="Insufficient data to generate verdict.",
        )

    await _flush_progress(state["job_id"], state["query"], {"task": "synthesis", "status": "complete", "message": "Report complete!"}, new_errors)

    return {
        "final_report": final_report,
        "errors": new_errors,
    }


def build_graph() -> StateGraph:
    builder = StateGraph(ReviewLensState)

    builder.add_node("enrich_query_node", enrich_query_node)
    builder.add_node("scraper_node", scraper_node)
    builder.add_node("analysis_node", analysis_node)
    builder.add_node("synthesis_node", synthesis_node)

    # Launch both in parallel by branching from START
    from langgraph.graph import START
    builder.add_edge(START, "enrich_query_node")
    builder.add_edge(START, "scraper_node")
    
    # Both paths converge at analysis_node
    builder.add_edge("enrich_query_node", "analysis_node")
    builder.add_edge("scraper_node", "analysis_node")
    
    builder.add_edge("analysis_node", "synthesis_node")
    builder.add_edge("synthesis_node", END)

    return builder.compile()

review_lens_graph = build_graph()

