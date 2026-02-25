from __future__ import annotations

import asyncio
import logging
from typing import Optional

import numpy as np

from models import RawReview, ReviewCluster
from config import get_settings

logger = logging.getLogger(__name__)


async def _name_cluster(llm, sample_reviews: list[RawReview]) -> str:
    from langchain_core.messages import HumanMessage

    sample_texts = "\n".join(f"- {r.text[:200]}" for r in sample_reviews[:5])
    prompt = f"""These reviews share a common theme. In 3-5 words, name the theme.
Reviews:
{sample_texts}
Theme:"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        theme = response.content.strip()
        # Clean up the response - take first line only
        theme = theme.split("\n")[0].strip()
        if len(theme) > 60:
            theme = theme[:57] + "..."
        return theme
    except Exception as e:
        logger.warning(f"Cluster naming failed: {e}")
        return "General Feedback"


def _determine_cluster_sentiment(reviews: list[RawReview]) -> str:
    rated = [r for r in reviews if r.rating is not None]
    if not rated:
        return "mixed"

    avg = sum(r.rating for r in rated) / len(rated)
    if avg >= 3.7:
        return "positive"
    elif avg <= 2.3:
        return "negative"
    else:
        return "mixed"


def _get_top_quotes(reviews: list[RawReview], n: int = 3) -> list[str]:
    # Sort by helpful_votes descending, then pick reviews with suitable text length
    sorted_reviews = sorted(reviews, key=lambda r: r.helpful_votes, reverse=True)
    quotes: list[str] = []
    for r in sorted_reviews:
        text = r.text.strip()
        if 50 <= len(text) <= 500:
            quotes.append(text[:500])
        elif len(text) > 500:
            quotes.append(text[:497] + "...")
        if len(quotes) >= n:
            break
    return quotes


async def cluster_reviews(reviews: list[RawReview]) -> list[ReviewCluster]:
    if len(reviews) < 10:
        logger.info("Too few reviews for clustering (< 10), skipping")
        return []

    settings = get_settings()

    from langchain_ollama import ChatOllama
    from sentence_transformers import SentenceTransformer
    import umap
    import hdbscan

    # Generate embeddings
    logger.debug("Generating embeddings for clustering...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [r.text[:512] for r in reviews]

    try:
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []

    # UMAP dimensionality reduction
    logger.debug("Running UMAP...")
    n_neighbors = min(15, len(reviews) - 1)
    try:
        reducer = umap.UMAP(
            n_components=5,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            random_state=42,
            verbose=False,
        )
        reduced = reducer.fit_transform(embeddings)
    except Exception as e:
        logger.error(f"UMAP failed: {e}")
        return []

    # HDBSCAN clustering
    logger.debug("Running HDBSCAN...")
    min_cluster_size = max(5, len(reviews) // 20)
    try:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            prediction_data=True,
        )
        labels = clusterer.fit_predict(reduced)
    except Exception as e:
        logger.error(f"HDBSCAN failed: {e}")
        return []

    unique_labels = set(labels)
    unique_labels.discard(-1)  # Remove noise label

    if not unique_labels:
        logger.info("HDBSCAN found no clusters")
        return []

    llm = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_model)

    # Build cluster data and name all clusters concurrently
    cluster_data = []
    for label in sorted(unique_labels):
        cluster_indices = [i for i, l in enumerate(labels) if l == label]
        cluster_revs = [reviews[i] for i in cluster_indices]
        cluster_data.append((int(label), cluster_revs))

    themes = await asyncio.gather(*[_name_cluster(llm, cd[1]) for cd in cluster_data])

    clusters: list[ReviewCluster] = []
    for (label, cluster_revs), theme in zip(cluster_data, themes):
        clusters.append(
            ReviewCluster(
                cluster_id=label,
                theme=theme,
                review_count=len(cluster_revs),
                sentiment=_determine_cluster_sentiment(cluster_revs),
                top_quotes=_get_top_quotes(cluster_revs, n=3),
            )
        )

    clusters.sort(key=lambda c: c.review_count, reverse=True)
    logger.info(f"Clustering: {len(clusters)} clusters found from {len(reviews)} reviews")
    return clusters
