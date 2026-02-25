from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class RawReview(BaseModel):
    id: str
    source: str  # "amazon" | "reddit" | "bestbuy" | "youtube"
    text: str
    rating: Optional[float] = None
    date: Optional[datetime] = None
    verified_purchase: bool = False
    helpful_votes: int = 0
    reviewer_id: Optional[str] = None
    fake_score: float = 0.0


class ReviewAspect(BaseModel):
    aspect: str
    sentiment: Literal["positive", "negative", "mixed", "neutral"]
    score: float
    representative_quote: str
    mention_count: int


class FakeReviewReport(BaseModel):
    total_reviews: int
    flagged_count: int
    fake_percentage: float
    flagged_ids: list[str]
    risk_level: Literal["low", "medium", "high"]


class DriftReport(BaseModel):
    monthly_sentiment: list[dict]
    change_points: list[str]
    trend: Literal["improving", "declining", "stable"]


class ReviewCluster(BaseModel):
    cluster_id: int
    theme: str
    review_count: int
    sentiment: Literal["positive", "negative", "mixed"]
    top_quotes: list[str]


class FinalReport(BaseModel):
    product_name: str
    image_url: Optional[str] = None
    overall_score: float
    total_reviews_analyzed: int
    sources_used: list[str]
    sentiment_breakdown: dict
    aspect_scores: list[ReviewAspect]
    fake_report: FakeReviewReport
    drift_report: DriftReport
    clusters: list[ReviewCluster]
    featured_reviews: list[RawReview]
    executive_summary: str
    who_should_buy: str
    who_should_skip: str
    verdict: str


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    use_cache: bool = True


class AnalyzeResponse(BaseModel):
    job_id: str


class HealthResponse(BaseModel):
    status: str
    ollama: str
    postgres: str
    redis: str
