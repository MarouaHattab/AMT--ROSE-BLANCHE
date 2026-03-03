from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from controllers import SearchController
from models import ResponseSignal
from routes.schemes.search import SearchRequest
from helpers.metrics import (
    SEARCH_REQUESTS_TOTAL, SEARCH_LATENCY, SEARCH_COSINE_SCORE,
    SEARCH_AVG_SCORE, SEARCH_TOP_K, SEARCH_RESULTS_COUNT,
)
import logging
import time

logger = logging.getLogger("uvicorn.error")

search_router = APIRouter(
    prefix="/api/v1/search",
    tags=["api_v1", "search"],
)


@search_router.post("/")
async def semantic_search(request: Request, search_request: SearchRequest):
    """
    Semantic search endpoint using cosine similarity.
    
    Pipeline:
      1. Receive question
      2. Generate embedding with all-MiniLM-L6-v2 (384D)
      3. Compute cosine similarity against indexed embeddings
      4. Rank by similarity score descending
      5. Return top K fragments with text + score
    """
    start_time = time.time()
    SEARCH_TOP_K.observe(search_request.top_k)

    search_controller = SearchController(
        embedding_service=request.app.embedding_service,
        vectordb_client=request.app.vectordb_client,
    )

    try:
        results = await search_controller.search(
            question=search_request.question,
            top_k=search_request.top_k,
        )
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        SEARCH_REQUESTS_TOTAL.labels(status="error").inc()
        return JSONResponse(
            status_code=500,
            content={
                "signal": ResponseSignal.SEARCH_ERROR.value,
                "error": str(e),
            }
        )

    if not results:
        SEARCH_REQUESTS_TOTAL.labels(status="no_results").inc()
        SEARCH_LATENCY.observe(time.time() - start_time)
        SEARCH_RESULTS_COUNT.observe(0)
        return JSONResponse(
            status_code=404,
            content={
                "signal": ResponseSignal.SEARCH_NO_RESULTS.value,
                "question": search_request.question,
                "results": [],
            }
        )

    # Format results: rank, text, score, document_id
    formatted_results = []
    for i, result in enumerate(results, 1):
        formatted_results.append({
            "rank": i,
            "text": result.text,
            "score": result.score,
            "document_id": result.document_id,
        })

    # Metrics
    scores = [r.score for r in results]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    min_score = round(min(scores), 4) if scores else 0.0
    max_score = round(max(scores), 4) if scores else 0.0
    unique_docs = len({r.document_id for r in results})

    search_metrics = {
        "average_score": avg_score,
        "min_score": min_score,
        "max_score": max_score,
        "unique_documents": unique_docs,
        "total_results": len(results),
        "latency_ms": round((time.time() - start_time) * 1000, 1),
        "method": "cosine_similarity",
        "model": "all-MiniLM-L6-v2",
        "dimension": 384,
    }

    # Record Prometheus metrics
    SEARCH_REQUESTS_TOTAL.labels(status="success").inc()
    SEARCH_LATENCY.observe(time.time() - start_time)
    SEARCH_RESULTS_COUNT.observe(len(results))
    SEARCH_AVG_SCORE.observe(avg_score)
    for s in scores:
        SEARCH_COSINE_SCORE.observe(s)

    return JSONResponse(
        content={
            "signal": ResponseSignal.SEARCH_SUCCESS.value,
            "question": search_request.question,
            "top_k": search_request.top_k,
            "results": formatted_results,
            "metrics": search_metrics,
        }
    )


@search_router.get("/stats")
async def search_stats(request: Request):
    """Get statistics about the indexed embeddings."""
    try:
        count = await request.app.vectordb_client.get_embeddings_count()
        return JSONResponse(
            content={
                "signal": ResponseSignal.EMBEDDINGS_COUNT.value,
                "total_embeddings": count,
                "model": "all-MiniLM-L6-v2",
                "dimension": 384,
                "similarity_method": "cosine",
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "signal": ResponseSignal.DATABASE_ERROR.value,
                "error": str(e),
            }
        )


@search_router.get("/health")
async def search_health(request: Request):
    """Health check for search service."""
    try:
        count = await request.app.vectordb_client.get_embeddings_count()
        return JSONResponse(
            content={
                "status": "healthy",
                "embeddings_indexed": count,
                "ready": count > 0,
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            }
        )
