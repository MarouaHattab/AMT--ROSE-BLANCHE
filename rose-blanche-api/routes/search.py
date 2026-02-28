from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from controllers import SearchController
from models import ResponseSignal
from routes.schemes.search import SearchRequest
import logging

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
    search_controller = SearchController(
        embedding_service=request.app.embedding_service,
        vectordb_client=request.app.vectordb_client,
    )

    results, detected_ingredients = await search_controller.search(
        question=search_request.question,
        top_k=search_request.top_k,
    )

    if not results:
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
