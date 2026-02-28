from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from controllers import SearchController
from models import ResponseSignal
from routes.schemes.search import SearchRequest
from helpers.metrics import (
    SEARCH_REQUESTS_TOTAL, SEARCH_LATENCY, SEARCH_COSINE_SCORE,
    SEARCH_AVG_SCORE, SEARCH_TOP_K, SEARCH_RESULTS_COUNT,
    INGREDIENT_COVERAGE, INGREDIENTS_DETECTED, INGREDIENTS_COVERED,
)
import logging
import time

# ── Ingredient alias lookup for coverage check ─────────────────────
_INGREDIENT_ALIAS_MAP = {
    "ascorbic acid": ["ascorbic", "acide ascorbique", "e300", "vitamin c"],
    "alpha-amylase": ["alpha-amylase", "α-amylase", "fungal amylase", "amylase fongique"],
    "xylanase": ["xylanase", "endo-xylanase", "hemicellulose"],
    "lipase": ["lipase", "phospholipase"],
    "glucose oxidase": ["glucose oxidase", "glucose oxydase", "gox"],
    "transglutaminase": ["transglutaminase"],
    "amyloglucosidase": ["amyloglucosidase", "glucoamylase", "amg"],
    "maltogenic amylase": ["maltogenic", "anti-staling", "a fresh", "a soft"],
}

def _ingredient_aliases(ingredient: str) -> list:
    return _INGREDIENT_ALIAS_MAP.get(ingredient, [ingredient])

logger = logging.getLogger("uvicorn.error")

search_router = APIRouter(
    prefix="/api/v1/search",
    tags=["api_v1", "search"],
)


@search_router.post("/")
async def semantic_search(request: Request, search_request: SearchRequest):
    start_time = time.time()
    SEARCH_TOP_K.observe(search_request.top_k)

    search_controller = SearchController(
        embedding_service=request.app.embedding_service,
        vectordb_client=request.app.vectordb_client,
    )

    results, detected_ingredients = await search_controller.search(
        question=search_request.question,
        top_k=search_request.top_k,
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

    # Format results
    formatted_results = []
    for i, result in enumerate(results, 1):
        formatted_results.append({
            "rank": i,
            "text": result.text,
            "score": result.score,
            "document_id": result.document_id,
        })

    # ── Accuracy / quality metrics ─────────────────────────────────
    scores = [r.score for r in results]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    min_score = round(min(scores), 4) if scores else 0.0
    max_score = round(max(scores), 4) if scores else 0.0
    unique_docs = len({r.document_id for r in results})

    # Coverage: what fraction of detected ingredients appear in results
    if detected_ingredients:
        covered = 0
        for ing in detected_ingredients:
            # Check if any result text mentions this ingredient
            for r in results:
                if ing.lower() in r.text.lower() or \
                   any(alias in r.text.lower()
                       for alias in _ingredient_aliases(ing)):
                    covered += 1
                    break
        ingredient_coverage = round(covered / len(detected_ingredients), 4)
    else:
        ingredient_coverage = None

    metrics = {
        "average_score": avg_score,
        "min_score": min_score,
        "max_score": max_score,
        "unique_documents": unique_docs,
        "total_results": len(results),
    }
    if detected_ingredients:
        metrics["detected_ingredients"] = detected_ingredients
        metrics["ingredient_coverage"] = ingredient_coverage
        metrics["coverage_detail"] = (
            f"{covered}/{len(detected_ingredients)} ingredients found in results"
        )

    # ── Record Prometheus metrics ──────────────────────────────────
    SEARCH_REQUESTS_TOTAL.labels(status="success").inc()
    SEARCH_LATENCY.observe(time.time() - start_time)
    SEARCH_RESULTS_COUNT.observe(len(results))
    SEARCH_AVG_SCORE.observe(avg_score)
    for s in scores:
        SEARCH_COSINE_SCORE.observe(s)
    if detected_ingredients:
        for ing in detected_ingredients:
            INGREDIENTS_DETECTED.labels(ingredient=ing).inc()
        INGREDIENT_COVERAGE.observe(ingredient_coverage)
        # Track which ingredients were covered
        for ing in detected_ingredients:
            for r in results:
                if ing.lower() in r.text.lower() or \
                   any(alias in r.text.lower()
                       for alias in _ingredient_aliases(ing)):
                    INGREDIENTS_COVERED.labels(ingredient=ing).inc()
                    break

    return JSONResponse(
        content={
            "signal": ResponseSignal.SEARCH_SUCCESS.value,
            "question": search_request.question,
            "top_k": search_request.top_k,
            "results": formatted_results,
            "metrics": metrics,
        }
    )


@search_router.get("/stats")
async def search_stats(request: Request):
    """Get statistics about the embeddings in the database."""
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
