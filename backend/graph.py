from __future__ import annotations

import asyncio
import logging
from typing import TypedDict

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


class ReviewLensState(TypedDict):
    query: str
    enriched_queries: list[str]
    raw_reviews: list[RawReview]
    cleaned_reviews: list[RawReview]
    aspect_scores: list[ReviewAspect]
    fake_report: FakeReviewReport
    drift_report: DriftReport
    clusters: list[ReviewCluster]
    final_report: FinalReport
    progress: list[str]
    errors: list[str]


async def enrich_query_node(state: ReviewLensState) -> ReviewLensState:
    from agents.synthesis_agent import enrich_query

    query = state["query"]
    progress = list(state.get("progress", []))
    errors = list(state.get("errors", []))

    progress.append("Enriching query with LLM...")
    try:
        enriched = await enrich_query(query)
    except Exception as e:
        logger.warning(f"Query enrichment failed: {e}")
        errors.append(f"Query enrichment failed: {e}")
        enriched = [query]

    return {
        **state,
        "enriched_queries": enriched,
        "progress": progress,
        "errors": errors,
    }


async def scraper_node(state: ReviewLensState) -> ReviewLensState:
    from scrapers.amazon import scrape_amazon
    from scrapers.reddit import scrape_reddit
    from scrapers.bestbuy import scrape_bestbuy
    from scrapers.youtube import scrape_youtube

    query = state["query"]
    progress = list(state.get("progress", []))
    errors = list(state.get("errors", []))
    all_reviews: list[RawReview] = []

    progress.append("Scraping reviews from all sources...")

    async def safe_scrape(scraper_fn, name: str, *args) -> list[RawReview]:
        try:
            progress.append(f"Scraping {name}...")
            results = await scraper_fn(*args)
            progress.append(f"Scraped {len(results)} reviews from {name}")
            return results
        except Exception as e:
            logger.warning(f"Scraper {name} failed: {e}")
            errors.append(f"{name} scraper failed: {e}")
            return []

    results = await asyncio.gather(
        safe_scrape(scrape_amazon, "Amazon", query),
        safe_scrape(scrape_reddit, "Reddit", query),
        safe_scrape(scrape_bestbuy, "Best Buy", query),
        safe_scrape(scrape_youtube, "YouTube", query),
    )

    for batch in results:
        all_reviews.extend(batch)

    if not all_reviews:
        errors.append("No reviews collected from any source")

    progress.append(f"Total reviews collected: {len(all_reviews)}")

    return {
        **state,
        "raw_reviews": all_reviews,
        "cleaned_reviews": all_reviews,
        "progress": progress,
        "errors": errors,
    }


async def analysis_node(state: ReviewLensState) -> ReviewLensState:
    from analysis.absa import run_absa
    from analysis.fake_detector import detect_fake_reviews
    from analysis.drift_detector import detect_drift
    from analysis.clusterer import cluster_reviews

    reviews = state.get("cleaned_reviews", [])
    progress = list(state.get("progress", []))
    errors = list(state.get("errors", []))

    # ABSA
    progress.append("Running aspect-based sentiment analysis...")
    try:
        aspect_scores, reviews_with_fake = await run_absa(reviews)
    except Exception as e:
        logger.error(f"ABSA failed: {e}")
        errors.append(f"ABSA failed: {e}")
        aspect_scores = []
        reviews_with_fake = reviews

    # Fake detection
    progress.append("Detecting fake reviews...")
    try:
        fake_report, reviews_scored = detect_fake_reviews(reviews_with_fake)
    except Exception as e:
        logger.error(f"Fake detection failed: {e}")
        errors.append(f"Fake detection failed: {e}")
        fake_report = FakeReviewReport(
            total_reviews=len(reviews),
            flagged_count=0,
            fake_percentage=0.0,
            flagged_ids=[],
            risk_level="low",
        )
        reviews_scored = reviews

    # Drift detection
    progress.append("Analyzing sentiment drift over time...")
    try:
        drift_report = detect_drift(reviews_scored)
    except Exception as e:
        logger.error(f"Drift detection failed: {e}")
        errors.append(f"Drift detection failed: {e}")
        drift_report = DriftReport(monthly_sentiment=[], change_points=[], trend="stable")

    # Clustering
    progress.append("Clustering reviews by theme...")
    try:
        clusters = await cluster_reviews(reviews_scored)
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        errors.append(f"Clustering failed: {e}")
        clusters = []

    return {
        **state,
        "cleaned_reviews": reviews_scored,
        "aspect_scores": aspect_scores,
        "fake_report": fake_report,
        "drift_report": drift_report,
        "clusters": clusters,
        "progress": progress,
        "errors": errors,
    }


async def synthesis_node(state: ReviewLensState) -> ReviewLensState:
    from agents.synthesis_agent import synthesize_report

    progress = list(state.get("progress", []))
    errors = list(state.get("errors", []))

    progress.append("Synthesizing final report...")
    try:
        final_report = await synthesize_report(state)
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        errors.append(f"Synthesis failed: {e}")
        # Build minimal report
        reviews = state.get("cleaned_reviews", [])
        sources = list({r.source for r in reviews})
        final_report = FinalReport(
            product_name=state["query"],
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

    progress.append("Report complete!")

    return {
        **state,
        "final_report": final_report,
        "progress": progress,
        "errors": errors,
    }


def build_graph() -> StateGraph:
    builder = StateGraph(ReviewLensState)

    builder.add_node("enrich_query_node", enrich_query_node)
    builder.add_node("scraper_node", scraper_node)
    builder.add_node("analysis_node", analysis_node)
    builder.add_node("synthesis_node", synthesis_node)

    builder.set_entry_point("enrich_query_node")
    builder.add_edge("enrich_query_node", "scraper_node")
    builder.add_edge("scraper_node", "analysis_node")
    builder.add_edge("analysis_node", "synthesis_node")
    builder.add_edge("synthesis_node", END)

    return builder.compile()


review_lens_graph = build_graph()
