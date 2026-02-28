from fastapi import APIRouter, Depends
from helpers.config import get_settings, Settings

base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@base_router.get("/")
async def welcome(app_settings: Settings = Depends(get_settings)):
    return {
        "app_name": app_settings.APP_NAME,
        "app_version": app_settings.APP_VERSION,
        "description": "RAG Semantic Search Module - AMT Rose Blanche Challenge",
        "model": "all-MiniLM-L6-v2",
        "dimension": 384,
        "similarity": "cosine",
        "top_k": app_settings.DEFAULT_TOP_K,
    }
