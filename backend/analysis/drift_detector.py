from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timezone

import ruptures as rpt

from models import RawReview, DriftReport

logger = logging.getLogger(__name__)


def detect_drift(reviews: list[RawReview]) -> DriftReport:
    # Filter reviews with both date and rating
    dated_reviews = [r for r in reviews if r.date is not None and r.rating is not None]

    if len(dated_reviews) < 3:
        return DriftReport(monthly_sentiment=[], change_points=[], trend="stable")

    # Group by year-month
    monthly: dict[str, list[float]] = defaultdict(list)
    for r in dated_reviews:
        try:
            date_aware = r.date.replace(tzinfo=timezone.utc) if r.date.tzinfo is None else r.date
            month_key = date_aware.strftime("%Y-%m")
            normalized = (r.rating - 1.0) / 4.0  # 1-5 stars → 0-1
            monthly[month_key].append(normalized)
        except Exception as e:
            logger.debug(f"Error processing review date: {e}")
            continue

    if not monthly:
        return DriftReport(monthly_sentiment=[], change_points=[], trend="stable")

    sorted_months = sorted(monthly.keys())
    monthly_averages = [
        {"month": m, "avg_sentiment": round(sum(monthly[m]) / len(monthly[m]), 4)}
        for m in sorted_months
    ]

    # Change-point detection
    change_points: list[str] = []
    if len(sorted_months) >= 4:
        signal = [ma["avg_sentiment"] for ma in monthly_averages]
        try:
            algo = rpt.Pelt(model="rbf").fit(signal)
            breakpoints = algo.predict(pen=10)
            # breakpoints are indices (1-indexed end of segment), exclude last (len)
            for bp in breakpoints[:-1]:
                idx = min(bp, len(sorted_months) - 1)
                change_points.append(sorted_months[idx])
        except Exception as e:
            logger.warning(f"Change-point detection failed: {e}")

    # Compute trend: compare last 3 months vs first 3 months
    trend: str = "stable"
    if len(monthly_averages) >= 6:
        first_3 = [ma["avg_sentiment"] for ma in monthly_averages[:3]]
        last_3 = [ma["avg_sentiment"] for ma in monthly_averages[-3:]]
        first_avg = sum(first_3) / len(first_3)
        last_avg = sum(last_3) / len(last_3)
        delta = last_avg - first_avg

        if delta > 0.05:
            trend = "improving"
        elif delta < -0.05:
            trend = "declining"
        else:
            trend = "stable"

    logger.info(f"Drift detection: {len(sorted_months)} months, {len(change_points)} change points, trend={trend}")
    return DriftReport(
        monthly_sentiment=monthly_averages,
        change_points=change_points,
        trend=trend,
    )
