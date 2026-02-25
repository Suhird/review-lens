from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from cache.redis_manager import (
    cache_report,
    get_cached_report,
    get_job_data,
    ping_redis,
    set_job_data,
)
from config import get_settings
from db.database import close_pool, ping_postgres, store_report, store_reviews, upsert_product
from models import AnalyzeRequest, AnalyzeResponse, FinalReport, HealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ReviewLens API",
    description="AI-powered consumer product review intelligence engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await close_pool()


async def _run_pipeline(job_id: str, query: str, use_cache: bool = True) -> None:
    """Run the full LangGraph pipeline and store results in Redis."""
    from graph import review_lens_graph
    from cache.redis_manager import normalize_name

    async def update_progress(message: str, step: int, total_steps: int = 8) -> None:
        job = await get_job_data(job_id) or {"status": "running", "progress": [], "errors": [], "report": None}
        job["progress"].append({"message": message, "step": step, "total_steps": total_steps})
        await set_job_data(job_id, job)

    try:
        await set_job_data(job_id, {
            "status": "running",
            "query": query,
            "progress": [],
            "errors": [],
            "report": None,
        })

        await update_progress("Starting analysis pipeline...", 1)

        initial_state = {
            "job_id": job_id,
            "query": query,
            "use_cache": use_cache,
            "enriched_queries": [],
            "raw_reviews": [],
            "product_image": None,
            "cleaned_reviews": [],
            "aspect_scores": [],
            "fake_report": None,
            "drift_report": None,
            "clusters": [],
            "final_report": None,
            "errors": [],
        }

        final_state = await review_lens_graph.ainvoke(initial_state)

        report: FinalReport = final_state.get("final_report")
        errors = final_state.get("errors", [])

        if report is None:
            raise ValueError("Pipeline completed without generating a report")

        # Persist to Redis
        await cache_report(query, report)

        # Persist to PostgreSQL (best-effort)
        try:
            norm = normalize_name(query)
            product_id = await upsert_product(norm, query)
            await store_reviews(product_id, final_state.get("cleaned_reviews", []))
            await store_report(product_id, report)
        except Exception as e:
            logger.warning(f"DB persistence failed (non-fatal): {e}")

        # Read accumulated progress from Redis (written by nodes during execution)
        existing_job = await get_job_data(job_id) or {}
        job_data = {
            "status": "complete",
            "query": query,
            "progress": existing_job.get("progress", []),
            "errors": errors,
            "report": json.loads(report.model_dump_json()),
        }
        await set_job_data(job_id, job_data)

    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
        job = await get_job_data(job_id) or {}
        job["status"] = "error"
        job["errors"] = job.get("errors", []) + [str(e)]
        await set_job_data(job_id, job)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Check cache
    if request.use_cache:
        cached = await get_cached_report(query)
        if cached:
            job_id = str(uuid.uuid4())
            await set_job_data(job_id, {
                "status": "complete",
                "query": query,
                "progress": [{"message": "Loaded from cache", "step": 8, "total_steps": 8}],
                "errors": [],
                "report": json.loads(cached.model_dump_json()),
            })
            return AnalyzeResponse(job_id=job_id)
            
        # Check database for previous analysis
        from db.database import get_report
        from cache.redis_manager import normalize_name
        norm = normalize_name(query)
        db_report = await get_report(norm)
        if db_report:
            await cache_report(query, db_report)
            job_id = str(uuid.uuid4())
            await set_job_data(job_id, {
                "status": "complete",
                "query": query,
                "progress": [{"message": "Loaded from database", "step": 8, "total_steps": 8}],
                "errors": [],
                "report": json.loads(db_report.model_dump_json()),
            })
            return AnalyzeResponse(job_id=job_id)

    job_id = str(uuid.uuid4())
    background_tasks.add_task(_run_pipeline, job_id, query, request.use_cache)
    return AnalyzeResponse(job_id=job_id)


async def _sse_generator(job_id: str) -> AsyncGenerator[str, None]:
    last_progress_idx = 0
    max_polls = 360  # 30 minutes max (5s intervals)

    for _ in range(max_polls):
        job = await get_job_data(job_id)

        if job is None:
            yield _sse_event("error", {"message": "Job not found"})
            return

        status = job.get("status", "running")
        progress_list = job.get("progress", [])

        # Stream new progress events
        for i in range(last_progress_idx, len(progress_list)):
            entry = progress_list[i]
            if isinstance(entry, dict):
                yield _sse_event("progress", entry)
            else:
                yield _sse_event("progress", {"message": str(entry), "step": i + 1, "total_steps": 8})
        last_progress_idx = len(progress_list)

        if status == "complete":
            report_data = job.get("report")
            if report_data:
                yield _sse_event("complete", {"data": report_data})
            return

        if status == "error":
            errors = job.get("errors", ["Unknown error"])
            yield _sse_event("error", {"message": errors[-1] if errors else "Unknown error"})
            return

        await asyncio.sleep(5)

    yield _sse_event("error", {"message": "Analysis timed out"})


def _sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


@app.get("/api/stream/{job_id}")
async def stream_job(job_id: str) -> StreamingResponse:
    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/report/{job_id}", response_model=FinalReport)
async def get_report(job_id: str) -> FinalReport:
    job = await get_job_data(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "complete":
        raise HTTPException(status_code=202, detail="Report not ready yet")

    report_data = job.get("report")
    if not report_data:
        raise HTTPException(status_code=404, detail="Report data missing")

    return FinalReport.model_validate(report_data)


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()

    # Check Ollama
    ollama_status = "unhealthy"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                ollama_status = "healthy"
    except Exception:
        pass

    # Check PostgreSQL
    postgres_ok = await ping_postgres()
    postgres_status = "healthy" if postgres_ok else "unhealthy"

    # Check Redis
    redis_ok = await ping_redis()
    redis_status = "healthy" if redis_ok else "unhealthy"

    overall = "healthy" if all(s == "healthy" for s in [ollama_status, postgres_status, redis_status]) else "degraded"

    return HealthResponse(
        status=overall,
        ollama=ollama_status,
        postgres=postgres_status,
        redis=redis_status,
    )
