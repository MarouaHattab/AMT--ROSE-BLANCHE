from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator
from routes import base, search
from routes.data import data_router
from routes.tasks import tasks_router
from helpers.config import get_settings
from stores.embedding.EmbeddingService import EmbeddingService
from stores.vectordb.PGVectorProvider import PGVectorProvider
from models.db_schemes import SQLAlchemyBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

app = FastAPI(
    title="Rose Blanche RAG API",
    description=(
        "Semantic search module for bakery & pastry formulation assistance. "
        "Uses all-MiniLM-L6-v2 (384D) embeddings with cosine similarity "
        "to retrieve the top K most relevant fragments."
    ),
    version="2.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics instrumentation ──
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    excluded_handlers=["/metrics", "/health"],
    env_var_name="ENABLE_METRICS",
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)


async def startup_span():
    """Initialize database connection, embedding service, and vector DB."""
    import logging
    logger = logging.getLogger("uvicorn")
    settings = get_settings()

    # ── Database connection ──
    postgres_conn = (
        f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    )

    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # ── Enable pgvector extension before creating tables ──
    async with app.db_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # ── Create tables if they don't exist ──
    async with app.db_engine.begin() as conn:
        await conn.run_sync(SQLAlchemyBase.metadata.create_all)

    # ── Embedding service (all-MiniLM-L6-v2, 384D) ──
    app.embedding_service = EmbeddingService(model_id=settings.EMBEDDING_MODEL_ID)
    app.embedding_service.load_model()

    # ── Vector DB client (PGVector - cosine similarity) ──
    app.vectordb_client = PGVectorProvider(
        db_client=app.db_client,
        default_vector_size=settings.EMBEDDING_MODEL_SIZE,
        distance_method=settings.VECTOR_DB_DISTANCE_METHOD,
    )
    await app.vectordb_client.connect()

    # Log ready state
    try:
        count = await app.vectordb_client.get_embeddings_count()
        logger.info(f"Rose Blanche RAG ready - {count} embeddings indexed (cosine similarity, top_k={settings.DEFAULT_TOP_K})")

        # ── Auto-ingest: if DB is empty and AUTO_INGEST is enabled, trigger Celery task ──
        if count == 0 and settings.AUTO_INGEST:
            dataset_dir = settings.DATASET_DIR
            if os.path.exists(dataset_dir) and os.listdir(dataset_dir):
                try:
                    from celery_app import celery_app as celery
                    task = celery.send_task(
                        "tasks.ingestion_tasks.ingest_documents",
                        kwargs={"directory_path": dataset_dir},
                    )
                    logger.info(f"Auto-ingest triggered via Celery: task_id={task.id}, dataset={dataset_dir}")
                except Exception as ce:
                    logger.warning(f"Celery auto-ingest failed (broker down?): {ce}. Falling back to direct ingestion...")
                    # Fallback: ingest directly if Celery/RabbitMQ unavailable
                    from controllers import DataController
                    data_ctrl = DataController(embedding_service=app.embedding_service)
                    result = await data_ctrl.ingest_directory(
                        directory_path=dataset_dir,
                        db_client=app.db_client,
                    )
                    logger.info(f"Direct auto-ingest complete: {result['total_documents']} docs, {result['total_fragments']} fragments")
            else:
                logger.warning(f"AUTO_INGEST enabled but dataset dir not found or empty: {dataset_dir}")
    except Exception as e:
        logger.warning(f"Could not get embedding count: {e}")


async def shutdown_span():
    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()


app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)

app.include_router(base.base_router)
app.include_router(search.search_router)
app.include_router(data_router)
app.include_router(tasks_router)

# ── Static files & frontend ──────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(os.path.join(static_dir, "index.html"))
