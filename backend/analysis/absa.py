from __future__ import annotations

import json
import logging
from typing import Any

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from models import RawReview, ReviewAspect
from config import get_settings

logger = logging.getLogger(__name__)

ASPECTS = [
    "build quality",
    "performance",
    "value for money",
    "ease of use",
    "battery life",
    "design",
    "customer support",
    "durability",
    "features",
    "comfort",
]

ASPECT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "aspect": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "mixed", "neutral"]},
            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "representative_quote": {"type": "string"},
            "mention_count": {"type": "integer"},
        },
        "required": ["aspect", "sentiment", "score", "representative_quote", "mention_count"],
    },
}

ABSA_PROMPT_TEMPLATE = """You are a product review analyst. Analyze these reviews and extract aspect-based sentiment.
For each of these aspects determine: sentiment (positive/negative/mixed/neutral),
a score from 0.0 to 1.0, and the most representative quote.
Aspects: build quality, performance, value for money, ease of use, battery life,
design, customer support, durability, features, comfort.
Only include aspects actually mentioned in the reviews.
Reviews:
{batch_text}

Respond ONLY with valid JSON matching this schema:
{schema}

Do not include any text outside the JSON array."""

STRICT_ABSA_PROMPT_TEMPLATE = """You are a product review analyst. Return ONLY a valid JSON array, no other text.
Each element must have exactly these fields: aspect (string), sentiment (one of: positive, negative, mixed, neutral),
score (number 0.0-1.0), representative_quote (string), mention_count (integer).
Only include aspects from: build quality, performance, value for money, ease of use, battery life,
design, customer support, durability, features, comfort.
Only include aspects actually mentioned.

Reviews:
{batch_text}

JSON array only:"""


def _build_batches(reviews: list[RawReview], batch_size: int = 20) -> list[list[RawReview]]:
    return [reviews[i : i + batch_size] for i in range(0, len(reviews), batch_size)]


def _format_batch(batch: list[RawReview]) -> str:
    lines = []
    for i, r in enumerate(batch, 1):
        rating_str = f" ({r.rating}/5 stars)" if r.rating else ""
        lines.append(f"{i}. [{r.source}]{rating_str} {r.text[:500]}")
    return "\n".join(lines)


async def _call_llm_for_batch(
    llm: ChatOllama,
    batch: list[RawReview],
    strict: bool = False,
) -> list[dict[str, Any]] | None:
    batch_text = _format_batch(batch)
    schema_str = json.dumps(ASPECT_SCHEMA, indent=2)

    if strict:
        prompt = STRICT_ABSA_PROMPT_TEMPLATE.format(batch_text=batch_text)
    else:
        prompt = ABSA_PROMPT_TEMPLATE.format(batch_text=batch_text, schema=schema_str)

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Extract JSON array from response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return None

        json_str = raw[start:end]
        data = json.loads(json_str)
        if isinstance(data, list):
            return data
        return None
    except Exception as e:
        logger.debug(f"LLM ABSA call failed: {e}")
        return None


def _merge_aspect_results(all_results: list[list[dict[str, Any]]]) -> list[ReviewAspect]:
    aspect_accumulator: dict[str, dict] = {}

    for batch_results in all_results:
        for item in batch_results:
            aspect = item.get("aspect", "").lower().strip()
            if not aspect or aspect not in ASPECTS:
                continue

            if aspect not in aspect_accumulator:
                aspect_accumulator[aspect] = {
                    "scores": [],
                    "sentiments": [],
                    "quotes": [],
                    "mention_count": 0,
                }

            acc = aspect_accumulator[aspect]
            score = item.get("score", 0.5)
            if isinstance(score, (int, float)) and 0.0 <= score <= 1.0:
                acc["scores"].append(score)

            sentiment = item.get("sentiment", "neutral")
            if sentiment in ("positive", "negative", "mixed", "neutral"):
                acc["sentiments"].append(sentiment)

            quote = item.get("representative_quote", "")
            if quote:
                acc["quotes"].append(quote)

            acc["mention_count"] += item.get("mention_count", 1)

    merged: list[ReviewAspect] = []
    for aspect, data in aspect_accumulator.items():
        if not data["scores"]:
            continue

        avg_score = sum(data["scores"]) / len(data["scores"])

        # Determine dominant sentiment
        sentiment_counts: dict[str, int] = {}
        for s in data["sentiments"]:
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
        dominant_sentiment = max(sentiment_counts, key=lambda k: sentiment_counts[k], default="neutral")

        # Pick best quote (longest one under 200 chars)
        best_quote = ""
        for q in sorted(data["quotes"], key=len, reverse=True):
            if len(q) <= 200:
                best_quote = q
                break
        if not best_quote and data["quotes"]:
            best_quote = data["quotes"][0][:200]

        merged.append(
            ReviewAspect(
                aspect=aspect,
                sentiment=dominant_sentiment,
                score=round(avg_score, 3),
                representative_quote=best_quote,
                mention_count=data["mention_count"],
            )
        )

    return sorted(merged, key=lambda a: a.mention_count, reverse=True)


async def run_absa(reviews: list[RawReview]) -> tuple[list[ReviewAspect], list[RawReview]]:
    if not reviews:
        return [], reviews

    settings = get_settings()
    llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)
    batches = _build_batches(reviews, batch_size=20)
    all_batch_results: list[list[dict]] = []

    for i, batch in enumerate(batches):
        logger.debug(f"Processing ABSA batch {i + 1}/{len(batches)}")

        result = await _call_llm_for_batch(llm, batch, strict=False)

        if result is None:
            logger.warning(f"ABSA batch {i + 1} returned invalid JSON, retrying with strict prompt")
            result = await _call_llm_for_batch(llm, batch, strict=True)

        if result is None:
            logger.warning(f"ABSA batch {i + 1} failed after retry, skipping batch")
            continue

        all_batch_results.append(result)

    aspect_scores = _merge_aspect_results(all_batch_results)
    return aspect_scores, reviews
