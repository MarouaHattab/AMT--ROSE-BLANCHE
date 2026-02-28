from fastapi import APIRouter
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from celery_app import celery_app
from routes.schemes.search import IngestRequest
import logging

logger = logging.getLogger("uvicorn.error")

tasks_router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["api_v1", "tasks"],
)


@tasks_router.post("/ingest")
async def async_ingest(ingest_request: IngestRequest = None):
    """
    Submit an asynchronous ingestion job via Celery.
    Returns a task_id to poll for status.
    """
    if ingest_request is None:
        ingest_request = IngestRequest()

    task = celery_app.send_task(
        "tasks.ingestion_tasks.ingest_documents",
        kwargs={
            "chunk_size": ingest_request.chunk_size,
            "overlap_size": ingest_request.overlap_size,
            "directory_path": ingest_request.directory_path,
        },
    )

    return JSONResponse(
        status_code=202,
        content={
            "signal": "task_submitted",
            "task_id": task.id,
            "status": "PENDING",
            "message": "Ingestion task submitted. Poll /api/v1/tasks/{task_id} for status.",
        },
    )


@tasks_router.post("/reingest")
async def async_reingest(ingest_request: IngestRequest = None):
    """
    Submit an asynchronous re-ingestion job (drop + re-ingest) via Celery.
    """
    if ingest_request is None:
        ingest_request = IngestRequest()

    task = celery_app.send_task(
        "tasks.ingestion_tasks.reingest_documents",
        kwargs={
            "chunk_size": ingest_request.chunk_size,
            "overlap_size": ingest_request.overlap_size,
            "directory_path": ingest_request.directory_path,
        },
    )

    return JSONResponse(
        status_code=202,
        content={
            "signal": "task_submitted",
            "task_id": task.id,
            "status": "PENDING",
            "message": "Re-ingestion task submitted. Poll /api/v1/tasks/{task_id} for status.",
        },
    )


@tasks_router.get("/{task_id}")
async def get_task_status(task_id: str):
    """
    Poll the status of a Celery task by its ID.
    States: PENDING → PROGRESS → SUCCESS / FAILURE
    """
    result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.status == "PROGRESS":
        response["meta"] = result.info
    elif result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)

    return JSONResponse(content=response)


@tasks_router.delete("/{task_id}")
async def revoke_task(task_id: str):
    """
    Revoke (cancel) a pending or running Celery task.
    """
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    return JSONResponse(
        content={
            "task_id": task_id,
            "signal": "task_revoked",
            "message": f"Task {task_id} has been revoked.",
        }
    )


@tasks_router.get("/")
async def list_active_tasks():
    """
    List all active, reserved, and scheduled tasks across workers.
    """
    inspector = celery_app.control.inspect()

    active = inspector.active() or {}
    reserved = inspector.reserved() or {}
    scheduled = inspector.scheduled() or {}

    return JSONResponse(
        content={
            "active": {k: len(v) for k, v in active.items()},
            "reserved": {k: len(v) for k, v in reserved.items()},
            "scheduled": {k: len(v) for k, v in scheduled.items()},
            "active_details": active,
        }
    )
