from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse
from controllers import DataController
from models import ResponseSignal
from routes.schemes.search import IngestRequest
from typing import List
import os
import logging
import shutil

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)


@data_router.post("/upload")
async def upload_pdfs(request: Request, files: List[UploadFile] = File(...)):
    """
    Upload one or more PDF files, extract text, chunk, embed, and store.
    Supported formats: PDF, Markdown, TXT.
    """
    from helpers.config import get_settings

    settings = get_settings()
    upload_dir = settings.UPLOAD_DIR

    # Ensure upload directory exists
    os.makedirs(upload_dir, exist_ok=True)

    supported_extensions = {".pdf"}
    results = []
    total_documents = 0
    total_fragments = 0

    data_controller = DataController(
        embedding_service=request.app.embedding_service,
    )

    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if ext not in supported_extensions:
            results.append({
                "filename": filename,
                "status": "error",
                "reason": f"Unsupported file type: {ext}. Supported: {', '.join(supported_extensions)}",
                "fragments": 0,
            })
            continue

        # Save uploaded file to disk
        file_path = os.path.join(upload_dir, filename)
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
        except Exception as e:
            results.append({
                "filename": filename,
                "status": "error",
                "reason": f"Failed to save file: {str(e)}",
                "fragments": 0,
            })
            continue

        # Ingest the file
        try:
            result = await data_controller.ingest_file(
                file_path=file_path,
                db_client=request.app.db_client,
                chunk_size=settings.DEFAULT_CHUNK_SIZE,
                overlap_size=settings.DEFAULT_OVERLAP_SIZE,
            )
            results.append(result)
            if result["status"] == "success":
                total_documents += 1
                total_fragments += result["fragments"]
        except Exception as e:
            logger.error(f"Ingestion failed for {filename}: {str(e)}")
            results.append({
                "filename": filename,
                "status": "error",
                "reason": str(e),
                "fragments": 0,
            })

    return JSONResponse(
        content={
            "signal": ResponseSignal.UPLOAD_SUCCESS.value,
            "total_documents": total_documents,
            "total_fragments": total_fragments,
            "details": results,
        }
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
    """List all ingested documents with their embedding counts."""
    from models.DocumentModel import DocumentModel
    from models.EmbeddingModel import EmbeddingModel

    try:
        doc_model = await DocumentModel.create_instance(db_client=request.app.db_client)
        emb_model = await EmbeddingModel.create_instance(db_client=request.app.db_client)
        documents = await doc_model.get_all_documents()

        docs_list = []
        for doc in documents:
            # Get fragment count per document
            fragments = await emb_model.get_embeddings_by_document(doc.id)
            docs_list.append({
                "id": doc.id,
                "filename": doc.nom_fichier,
                "title": doc.titre,
                "fragments": len(fragments),
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


@data_router.delete("/documents/{document_id}")
async def delete_document(request: Request, document_id: int):
    """Delete a document and all its embeddings."""
    from models.DocumentModel import DocumentModel
    from models.EmbeddingModel import EmbeddingModel

    try:
        doc_model = await DocumentModel.create_instance(db_client=request.app.db_client)
        emb_model = await EmbeddingModel.create_instance(db_client=request.app.db_client)

        # Check if document exists
        doc = await doc_model.get_document_by_id(document_id)
        if not doc:
            return JSONResponse(
                status_code=404,
                content={
                    "signal": ResponseSignal.DOCUMENT_NOT_FOUND.value,
                    "error": f"Document with id {document_id} not found",
                }
            )

        # Delete embeddings first (foreign key)
        deleted_embeddings = await emb_model.delete_by_document(document_id)

        # Delete document
        await doc_model.delete_document(document_id)

        return JSONResponse(
            content={
                "signal": ResponseSignal.DOCUMENT_DELETED.value,
                "document_id": document_id,
                "filename": doc.nom_fichier,
                "deleted_embeddings": deleted_embeddings,
            }
        )
    except Exception as e:
        logger.error(f"Delete failed: {str(e)}")
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
    Ingests from both dataset directory and uploads directory.
    """
    from sqlalchemy import text as sql_text
    from helpers.config import get_settings

    if ingest_request is None:
        ingest_request = IngestRequest()

    settings = get_settings()

    try:
        # Step 1: Truncate all data
        async with request.app.db_client() as session:
            async with session.begin():
                await session.execute(sql_text("DELETE FROM embeddings"))
                await session.execute(sql_text("DELETE FROM documents"))
            await session.commit()
        logger.info("All existing data deleted for re-ingestion")

        data_controller = DataController(
            embedding_service=request.app.embedding_service,
        )

        total_documents = 0
        total_fragments = 0
        all_details = []

        # Step 2: Ingest from dataset directory
        dataset_dir = ingest_request.directory_path or settings.DATASET_DIR
        if os.path.exists(dataset_dir) and os.listdir(dataset_dir):
            result = await data_controller.ingest_directory(
                directory_path=dataset_dir,
                db_client=request.app.db_client,
                chunk_size=ingest_request.chunk_size,
                overlap_size=ingest_request.overlap_size,
            )
            total_documents += result["total_documents"]
            total_fragments += result["total_fragments"]
            all_details.extend(result["details"])

        # Step 3: Also ingest from uploads directory
        upload_dir = settings.UPLOAD_DIR
        if os.path.exists(upload_dir) and os.listdir(upload_dir):
            result = await data_controller.ingest_directory(
                directory_path=upload_dir,
                db_client=request.app.db_client,
                chunk_size=ingest_request.chunk_size,
                overlap_size=ingest_request.overlap_size,
            )
            total_documents += result["total_documents"]
            total_fragments += result["total_fragments"]
            all_details.extend(result["details"])

        return JSONResponse(
            content={
                "signal": ResponseSignal.INGESTION_SUCCESS.value,
                "action": "full_reingest",
                "total_documents": total_documents,
                "total_fragments": total_fragments,
                "details": all_details,
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
