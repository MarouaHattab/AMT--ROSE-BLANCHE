from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routes import base, data, search
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
        "RAG semantic search module for bakery & pastry formulation assistance. "
        "Uses all-MiniLM-L6-v2 (384D) embeddings and cosine similarity "
        "to retrieve the most relevant text fragments."
    ),
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def startup_span():
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

    # ── Embedding service (all-MiniLM-L6-v2) ──
    app.embedding_service = EmbeddingService(model_id=settings.EMBEDDING_MODEL_ID)
    app.embedding_service.load_model()

    # ── Vector DB client (PGVector) ──
    app.vectordb_client = PGVectorProvider(
        db_client=app.db_client,
        default_vector_size=settings.EMBEDDING_MODEL_SIZE,
        distance_method=settings.VECTOR_DB_DISTANCE_METHOD,
    )
    await app.vectordb_client.connect()

    # ── Auto-ingest dataset on startup ──
    if settings.AUTO_INGEST:
        dataset_dir = settings.DATASET_DIR
        import os
        if os.path.exists(dataset_dir) and os.listdir(dataset_dir):
            import logging
            logger = logging.getLogger("uvicorn")
            logger.info(f"Auto-ingesting dataset from: {dataset_dir}")
            from controllers import DataController
            data_controller = DataController(
                embedding_service=app.embedding_service,
            )
            try:
                result = await data_controller.ingest_directory(
                    directory_path=dataset_dir,
                    db_client=app.db_client,
                )
                logger.info(
                    f"Auto-ingest complete: {result['total_documents']} docs, "
                    f"{result['total_fragments']} fragments"
                )
            except Exception as e:
                logger.error(f"Auto-ingest failed: {e}")


async def shutdown_span():
    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()


app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(search.search_router)

# ── Static files & frontend ──────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(os.path.join(static_dir, "index.html"))
