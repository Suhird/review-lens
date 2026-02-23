from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from models import RawReview, FinalReport, ReviewAspect
from config import get_settings

if TYPE_CHECKING:
    from graph import ReviewLensState

logger = logging.getLogger(__name__)


async def enrich_query(query: str) -> list[str]:
    settings = get_settings()
    llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)

    prompt = f"""Given the product query "{query}", generate 3-5 search query variants and aliases
that would help find reviews of this product. Include the original query, common abbreviations,
model numbers if applicable, and related search terms.
Return ONLY a JSON array of strings, no other text.
Example: ["Sony WH-1000XM5", "Sony XM5", "Sony noise canceling headphones", "WH1000XM5 review"]
Query: {query}
JSON array:"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        import json
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > 0:
            variants = json.loads(raw[start:end])
            if isinstance(variants, list) and len(variants) > 0:
                return [str(v) for v in variants[:5]]
    except Exception as e:
        logger.warning(f"Query enrichment failed: {e}")

    return [query]


def _compute_overall_score(
    reviews: list[RawReview],
    fake_percentage: float,
    trend: str,
) -> float:
    rated = [r for r in reviews if r.rating is not None]
    if not rated:
        return 5.0

    avg_rating = sum(r.rating for r in rated) / len(rated)
    base_score = (avg_rating - 1.0) / 4.0 * 10.0  # normalize to 0-10

    fake_penalty = min(fake_percentage / 100.0 * 0.1 * 10.0, 1.0)

    if trend == "improving":
        drift_bonus = 0.3
    elif trend == "declining":
        drift_bonus = -0.3
    else:
        drift_bonus = 0.0

    overall = base_score - fake_penalty + drift_bonus
    return round(min(10.0, max(0.0, overall)), 1)


def _select_featured_reviews(
    reviews: list[RawReview],
    clusters: list[Any],
    n: int = 5,
) -> list[RawReview]:
    # Pick one per dominant cluster first, then fill with best overall
    featured: list[RawReview] = []
    used_ids: set[str] = set()

    def is_good_review(r: RawReview) -> bool:
        return (
            r.fake_score < 0.3
            and 100 <= len(r.text) <= 500
        )

    # Try to pick one per cluster
    for cluster in clusters[:5]:
        pass  # We don't have cluster-to-review mapping here; fill from overall

    # Fallback: sort by quality criteria
    candidates = sorted(
        reviews,
        key=lambda r: (
            1 if r.verified_purchase else 0,
            -r.fake_score,
            r.helpful_votes,
            1 if 100 <= len(r.text) <= 500 else 0,
        ),
        reverse=True,
    )

    for r in candidates:
        if r.id in used_ids:
            continue
        if is_good_review(r):
            featured.append(r)
            used_ids.add(r.id)
        if len(featured) >= n:
            break

    # Fill if we don't have enough
    for r in candidates:
        if len(featured) >= n:
            break
        if r.id not in used_ids:
            featured.append(r)
            used_ids.add(r.id)

    return featured[:n]


def _compute_sentiment_breakdown(reviews: list[RawReview]) -> dict:
    total = len(reviews)
    if total == 0:
        return {"positive": 0, "negative": 0, "neutral": 0}

    positive = sum(1 for r in reviews if r.rating and r.rating >= 4.0)
    negative = sum(1 for r in reviews if r.rating and r.rating <= 2.0)
    neutral = total - positive - negative

    return {
        "positive": round(positive / total * 100, 1),
        "negative": round(negative / total * 100, 1),
        "neutral": round(neutral / total * 100, 1),
        "total": total,
    }


async def _generate_executive_summary(
    llm: ChatOllama,
    product_name: str,
    overall_score: float,
    aspect_scores: list[ReviewAspect],
    fake_percentage: float,
    trend: str,
    themes: list[str],
) -> str:
    top_positive = [a for a in aspect_scores if a.sentiment == "positive"][:3]
    top_negative = [a for a in aspect_scores if a.sentiment in ("negative", "mixed")][:3]

    top_pos_str = ", ".join(f"{a.aspect} ({a.score:.2f})" for a in top_positive) or "None identified"
    top_neg_str = ", ".join(f"{a.aspect} ({a.score:.2f})" for a in top_negative) or "None identified"
    themes_str = ", ".join(themes[:5]) if themes else "No distinct themes identified"

    prompt = f"""You are a consumer product expert. Based on the analysis below, write a 3-paragraph
executive summary for a consumer considering buying this product.
Paragraph 1: Overall impression and standout strengths (cite specific aspects).
Paragraph 2: Key weaknesses and caveats.
Paragraph 3: Context — who is the target user, how it compares to expectations.
Product: {product_name}
Overall score: {overall_score}/10
Top positive aspects: {top_pos_str}
Top negative aspects: {top_neg_str}
Fake review risk: {fake_percentage:.1f}%
Sentiment trend: {trend}
Key themes: {themes_str}
Write in a neutral, trustworthy consumer journalism tone. No marketing language.
Write 3 paragraphs separated by blank lines:"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        logger.warning(f"Executive summary generation failed: {e}")
        return f"Analysis of {product_name} based on {len(aspect_scores)} identified aspects. Overall score: {overall_score}/10."


async def _generate_who_should(
    llm: ChatOllama,
    product_name: str,
    aspect_scores: list[ReviewAspect],
    overall_score: float,
    buy_or_skip: str,
) -> str:
    top_positive = [a for a in aspect_scores if a.sentiment == "positive"][:3]
    top_negative = [a for a in aspect_scores if a.sentiment in ("negative", "mixed")][:3]

    if buy_or_skip == "buy":
        prompt = f"""For the product "{product_name}" with overall score {overall_score}/10,
top strengths: {', '.join(a.aspect for a in top_positive)}.
Write 2-3 bullet points describing WHO SHOULD BUY this product.
Be specific about use cases, user types, and needs this product serves well.
Format as plain bullet points starting with "•". No header needed."""
    else:
        prompt = f"""For the product "{product_name}" with overall score {overall_score}/10,
main weaknesses: {', '.join(a.aspect for a in top_negative)}.
Write 2-3 bullet points describing WHO SHOULD SKIP this product.
Be specific about use cases, user types, or needs this product fails to serve.
Format as plain bullet points starting with "•". No header needed."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        logger.warning(f"Who should {buy_or_skip} generation failed: {e}")
        return f"• Unable to determine based on available data."


async def synthesize_report(state: "ReviewLensState") -> FinalReport:
    settings = get_settings()
    llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)

    query = state["query"]
    reviews = state.get("cleaned_reviews", [])
    aspect_scores = state.get("aspect_scores", [])
    fake_report = state.get("fake_report")
    drift_report = state.get("drift_report")
    clusters = state.get("clusters", [])

    sources_used = list({r.source for r in reviews})
    overall_score = _compute_overall_score(
        reviews,
        fake_report.fake_percentage if fake_report else 0.0,
        drift_report.trend if drift_report else "stable",
    )
    sentiment_breakdown = _compute_sentiment_breakdown(reviews)
    featured_reviews = _select_featured_reviews(reviews, clusters, n=5)
    themes = [c.theme for c in clusters]

    executive_summary = await _generate_executive_summary(
        llm=llm,
        product_name=query,
        overall_score=overall_score,
        aspect_scores=aspect_scores,
        fake_percentage=fake_report.fake_percentage if fake_report else 0.0,
        trend=drift_report.trend if drift_report else "stable",
        themes=themes,
    )

    who_should_buy = await _generate_who_should(
        llm=llm,
        product_name=query,
        aspect_scores=aspect_scores,
        overall_score=overall_score,
        buy_or_skip="buy",
    )

    who_should_skip = await _generate_who_should(
        llm=llm,
        product_name=query,
        aspect_scores=aspect_scores,
        overall_score=overall_score,
        buy_or_skip="skip",
    )

    # Generate verdict sentence
    score_desc = "excellent" if overall_score >= 8 else "good" if overall_score >= 6.5 else "average" if overall_score >= 5 else "below average"
    trend_desc = f" and sentiment is {drift_report.trend}" if drift_report else ""
    verdict = f"{query} earns a {score_desc} {overall_score}/10{trend_desc}."

    return FinalReport(
        product_name=query,
        overall_score=overall_score,
        total_reviews_analyzed=len(reviews),
        sources_used=sources_used,
        sentiment_breakdown=sentiment_breakdown,
        aspect_scores=aspect_scores,
        fake_report=fake_report,
        drift_report=drift_report,
        clusters=clusters,
        featured_reviews=featured_reviews,
        executive_summary=executive_summary,
        who_should_buy=who_should_buy,
        who_should_skip=who_should_skip,
        verdict=verdict,
    )
