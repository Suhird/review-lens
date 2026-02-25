from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest

from models import RawReview, FakeReviewReport

logger = logging.getLogger(__name__)

GENERIC_PRAISE_PHRASES = [
    "great product",
    "highly recommend",
    "amazing",
    "perfect",
    "excellent",
    "fantastic",
    "love it",
    "best ever",
    "awesome",
    "outstanding",
    "incredible",
    "wonderful",
    "superb",
    "brilliant",
]


def _compute_burst_score(
    reviews: list[RawReview],
    window_days: int = 3,
    burst_threshold: int = 10,
) -> dict[str, float]:
    dated = []
    for r in reviews:
        if r.date is not None:
            dt = r.date.replace(tzinfo=timezone.utc) if r.date.tzinfo is None else r.date
            dated.append((r.id, dt))
    if not dated:
        return {r.id: 0.0 for r in reviews}

    # Find bursts: windows where 10+ reviews were posted within ±3 days
    burst_ids: set[str] = set()
    timestamps = sorted(dated, key=lambda x: x[1])

    for i, (rid, dt) in enumerate(timestamps):
        count = 0
        for j, (_, dt2) in enumerate(timestamps):
            if abs((dt2 - dt).days) <= window_days:
                count += 1
        if count >= burst_threshold:
            burst_ids.add(rid)

    return {r.id: (1.0 if r.id in burst_ids else 0.0) for r in reviews}


def _extract_features(reviews: list[RawReview]) -> np.ndarray:
    now = datetime.now(timezone.utc)

    # Count reviews per reviewer
    reviewer_counts: dict[str, int] = defaultdict(int)
    for r in reviews:
        if r.reviewer_id:
            reviewer_counts[r.reviewer_id] += 1

    burst_scores = _compute_burst_score(reviews)

    features = []
    for r in reviews:
        text = r.text or ""
        words = text.split()
        word_count = max(len(words), 1)

        text_length = float(len(text))
        exclamation_count = float(text.count("!"))
        caps_ratio = float(sum(1 for c in text if c.isupper())) / max(len(text), 1)

        text_lower = text.lower()
        generic_count = sum(1 for phrase in GENERIC_PRAISE_PHRASES if phrase in text_lower)
        generic_praise_score = float(generic_count) / word_count

        verified = 1.0 if r.verified_purchase else 0.0
        helpful_votes = float(r.helpful_votes)

        if r.date:
            try:
                date_aware = r.date.replace(tzinfo=timezone.utc) if r.date.tzinfo is None else r.date
                days_since = float((now - date_aware).days)
            except Exception:
                days_since = 180.0
        else:
            days_since = 180.0

        reviewer_review_count = 1.0 if (r.reviewer_id and reviewer_counts[r.reviewer_id] == 1) else 0.0
        burst_score = burst_scores.get(r.id, 0.0)

        features.append([
            text_length,
            exclamation_count,
            caps_ratio,
            generic_praise_score,
            verified,
            helpful_votes,
            days_since,
            reviewer_review_count,
            burst_score,
        ])

    return np.array(features, dtype=float)


def detect_fake_reviews(reviews: list[RawReview]) -> tuple[FakeReviewReport, list[RawReview]]:
    if not reviews:
        return FakeReviewReport(
            total_reviews=0,
            flagged_count=0,
            fake_percentage=0.0,
            flagged_ids=[],
            risk_level="low",
        ), reviews

    if len(reviews) < 5:
        # Too few reviews for meaningful isolation forest
        for r in reviews:
            r.fake_score = 0.0
        return FakeReviewReport(
            total_reviews=len(reviews),
            flagged_count=0,
            fake_percentage=0.0,
            flagged_ids=[],
            risk_level="low",
        ), reviews

    X = _extract_features(reviews)

    clf = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
    clf.fit(X)

    # decision_function returns negative values for anomalies
    # anomaly_scores: more negative = more anomalous
    raw_scores = clf.decision_function(X)

    # Normalize to 0-1 where 1 = most anomalous
    min_score = raw_scores.min()
    max_score = raw_scores.max()
    score_range = max_score - min_score if max_score != min_score else 1.0
    normalized_scores = 1.0 - (raw_scores - min_score) / score_range

    flagged_ids: list[str] = []
    updated_reviews: list[RawReview] = []

    for i, review in enumerate(reviews):
        fake_score = float(normalized_scores[i])
        updated = review.model_copy(update={"fake_score": round(fake_score, 4)})
        updated_reviews.append(updated)
        if fake_score > 0.7:
            flagged_ids.append(review.id)

    total = len(updated_reviews)
    flagged_count = len(flagged_ids)
    fake_percentage = round((flagged_count / total) * 100, 1) if total > 0 else 0.0

    if fake_percentage < 15:
        risk_level = "low"
    elif fake_percentage < 35:
        risk_level = "medium"
    else:
        risk_level = "high"

    report = FakeReviewReport(
        total_reviews=total,
        flagged_count=flagged_count,
        fake_percentage=fake_percentage,
        flagged_ids=flagged_ids,
        risk_level=risk_level,
    )

    logger.info(f"Fake detection: {flagged_count}/{total} flagged ({fake_percentage}%), risk={risk_level}")
    return report, updated_reviews
