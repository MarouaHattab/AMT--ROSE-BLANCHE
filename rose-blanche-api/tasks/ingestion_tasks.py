from celery_app import celery_app
from helpers.config import get_settings
from stores.embedding.EmbeddingService import EmbeddingService
from controllers.DataController import DataController
from models.db_schemes import SQLAlchemyBase
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker, Session
import os
import logging
import time

logger = logging.getLogger(__name__)

# ── Synchronous DB helpers (Celery workers are sync) ──────────────


def _get_sync_engine():
    """Create a synchronous SQLAlchemy engine for Celery workers."""
    settings = get_settings()
    postgres_conn = (
        f"postgresql+psycopg2://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    )
    return create_engine(postgres_conn)


def _get_sync_session():
    """Create a synchronous session factory."""
    engine = _get_sync_engine()
    return sessionmaker(bind=engine)


def _get_embedding_service():
    """Load the embedding model for the worker."""
    settings = get_settings()
    svc = EmbeddingService(model_id=settings.EMBEDDING_MODEL_ID)
    svc.load_model()
    return svc


# ── Celery Tasks ──────────────────────────────────────────────────


@celery_app.task(bind=True, name="tasks.ingestion_tasks.ingest_documents")
def ingest_documents(self, chunk_size=None, overlap_size=None, directory_path=None):
    
    settings = get_settings()
    dataset_dir = directory_path or settings.DATASET_DIR

    if not os.path.exists(dataset_dir):
        return {
            "status": "FAILED",
            "error": f"Dataset directory not found: {dataset_dir}",
        }

    self.update_state(state="PROGRESS", meta={"step": "loading_model"})

    try:
        embedding_service = _get_embedding_service()
        data_controller = DataController(embedding_service=embedding_service)

        self.update_state(state="PROGRESS", meta={"step": "reading_files"})

        # Use synchronous ingestion
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker as async_sessionmaker

        async_conn = (
            f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
        )
        engine = create_async_engine(async_conn)
        db_client = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        self.update_state(state="PROGRESS", meta={"step": "ingesting"})

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                data_controller.ingest_directory(
                    directory_path=dataset_dir,
                    db_client=db_client,
                    chunk_size=chunk_size,
                    overlap_size=overlap_size,
                )
            )
        finally:
            loop.run_until_complete(engine.dispose())
            loop.close()

        return {
            "status": "COMPLETED",
            **result,
        }

    except Exception as e:
        logger.error(f"Celery ingest failed: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
        }


@celery_app.task(bind=True, name="tasks.ingestion_tasks.reingest_documents")
def reingest_documents(self, chunk_size=None, overlap_size=None, directory_path=None):
   
    settings = get_settings()
    dataset_dir = directory_path or settings.DATASET_DIR

    if not os.path.exists(dataset_dir):
        return {
            "status": "FAILED",
            "error": f"Dataset directory not found: {dataset_dir}",
        }

    try:
        self.update_state(state="PROGRESS", meta={"step": "clearing_data"})

        # Truncate tables synchronously
        engine = _get_sync_engine()
        with engine.connect() as conn:
            conn.execute(sql_text("DELETE FROM embeddings"))
            conn.execute(sql_text("DELETE FROM documents"))
            conn.commit()
        engine.dispose()

        logger.info("All existing data deleted for re-ingestion")

        self.update_state(state="PROGRESS", meta={"step": "re_ingesting"})

        # Re-ingest using the ingest task logic
        embedding_service = _get_embedding_service()
        data_controller = DataController(embedding_service=embedding_service)

        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker as async_sessionmaker

        async_conn = (
            f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
        )
        async_engine = create_async_engine(async_conn)
        db_client = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                data_controller.ingest_directory(
                    directory_path=dataset_dir,
                    db_client=db_client,
                    chunk_size=chunk_size,
                    overlap_size=overlap_size,
                )
            )
        finally:
            loop.run_until_complete(async_engine.dispose())
            loop.close()

        return {
            "status": "COMPLETED",
            "action": "full_reingest",
            **result,
        }

    except Exception as e:
        logger.error(f"Celery re-ingest failed: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
        }


@celery_app.task(name="tasks.ingestion_tasks.health_check")
def health_check():
    
    try:
        engine = _get_sync_engine()
        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        engine.dispose()

        return {
            "status": "HEALTHY",
            "database": "connected",
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "UNHEALTHY",
            "error": str(e),
            "timestamp": time.time(),
        }


@celery_app.task(name="tasks.ingestion_tasks.scheduled_reingest")
def scheduled_reingest(chunk_size=500, overlap_size=50):
    logger.info("Scheduled re-ingestion triggered by Celery Beat")
    return reingest_documents(
        chunk_size=chunk_size,
        overlap_size=overlap_size,
    )
