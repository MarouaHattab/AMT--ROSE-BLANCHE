from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from controllers import DataController
from models import ResponseSignal
from routes.schemes.search import IngestRequest
import os
import logging

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)


@data_router.post("/ingest")
async def ingest_documents(request: Request, ingest_request: IngestRequest = None):
    if ingest_request is None:
        ingest_request = IngestRequest()

    # Determine dataset directory
    if ingest_request.directory_path:
        dataset_dir = ingest_request.directory_path
    else:
        from helpers.config import get_settings
        dataset_dir = get_settings().DATASET_DIR

    if not os.path.exists(dataset_dir):
        return JSONResponse(
            status_code=400,
            content={
                "signal": ResponseSignal.INGESTION_FAILED.value,
                "error": f"Dataset directory not found: {dataset_dir}",
            }
        )

    data_controller = DataController(
        embedding_service=request.app.embedding_service,
    )

    try:
        result = await data_controller.ingest_directory(
            directory_path=dataset_dir,
            db_client=request.app.db_client,
            chunk_size=ingest_request.chunk_size,
            overlap_size=ingest_request.overlap_size,
        )

        return JSONResponse(
            content={
                "signal": ResponseSignal.INGESTION_SUCCESS.value,
                **result,
            }
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "signal": ResponseSignal.INGESTION_FAILED.value,
                "error": str(e),
            }
        )


@data_router.get("/documents")
async def list_documents(request: Request):
    """List all ingested documents."""
    from models.DocumentModel import DocumentModel

    try:
        doc_model = await DocumentModel.create_instance(db_client=request.app.db_client)
        documents = await doc_model.get_all_documents()

        docs_list = []
        for doc in documents:
            docs_list.append({
                "id": doc.id,
                "filename": doc.nom_fichier,
                "title": doc.titre,
                "created_at": str(doc.created_at) if doc.created_at else None,
            })

        return JSONResponse(
            content={
                "signal": ResponseSignal.DOCUMENTS_LISTED.value,
                "total": len(docs_list),
                "documents": docs_list,
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


@data_router.get("/embeddings/count")
async def get_embeddings_count(request: Request):
    """Get the total number of embeddings stored."""
    try:
        count = await request.app.vectordb_client.get_embeddings_count()
        return JSONResponse(
            content={
                "signal": ResponseSignal.EMBEDDINGS_COUNT.value,
                "total": count,
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


@data_router.post("/reingest")
async def reingest_documents(request: Request, ingest_request: IngestRequest = None):
    """
    Drop all existing data and re-ingest from scratch.
    Use this after improving the chunking strategy.
    """
    from sqlalchemy import text as sql_text

    if ingest_request is None:
        ingest_request = IngestRequest()

    try:
        # Step 1: Truncate all data
        async with request.app.db_client() as session:
            async with session.begin():
                await session.execute(sql_text("DELETE FROM embeddings"))
                await session.execute(sql_text("DELETE FROM documents"))
            await session.commit()
        logger.info("All existing data deleted for re-ingestion")

        # Step 2: Determine dataset directory
        if ingest_request.directory_path:
            dataset_dir = ingest_request.directory_path
        else:
            from helpers.config import get_settings
            dataset_dir = get_settings().DATASET_DIR

        if not os.path.exists(dataset_dir):
            return JSONResponse(
                status_code=400,
                content={
                    "signal": ResponseSignal.INGESTION_FAILED.value,
                    "error": f"Dataset directory not found: {dataset_dir}",
                }
            )

        # Step 3: Re-ingest
        data_controller = DataController(
            embedding_service=request.app.embedding_service,
        )

        result = await data_controller.ingest_directory(
            directory_path=dataset_dir,
            db_client=request.app.db_client,
            chunk_size=ingest_request.chunk_size,
            overlap_size=ingest_request.overlap_size,
        )

        return JSONResponse(
            content={
                "signal": ResponseSignal.INGESTION_SUCCESS.value,
                "action": "full_reingest",
                **result,
            }
        )
    except Exception as e:
        logger.error(f"Re-ingestion failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "signal": ResponseSignal.INGESTION_FAILED.value,
                "error": str(e),
            }
        )
