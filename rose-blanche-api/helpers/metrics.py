from prometheus_client import Counter, Histogram, Gauge, Summary


# ── Search metrics ───────────────────────────────────────────────
SEARCH_REQUESTS_TOTAL = Counter(
    "rose_blanche_search_requests_total",
    "Total number of semantic search requests",
    ["status"],  # success / no_results / error
)

SEARCH_LATENCY = Histogram(
    "rose_blanche_search_latency_seconds",
    "Search request latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

SEARCH_COSINE_SCORE = Histogram(
    "rose_blanche_cosine_score",
    "Distribution of cosine similarity scores returned by search",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

SEARCH_AVG_SCORE = Summary(
    "rose_blanche_search_avg_score",
    "Average cosine score per search request",
)

SEARCH_TOP_K = Histogram(
    "rose_blanche_search_top_k",
    "Distribution of top_k values requested",
    buckets=[1, 2, 3, 5, 10, 20],
)

SEARCH_RESULTS_COUNT = Histogram(
    "rose_blanche_search_results_count",
    "Number of results returned per search",
    buckets=[0, 1, 2, 3, 5, 10, 20],
)

# ── Upload metrics ───────────────────────────────────────────────
UPLOAD_REQUESTS_TOTAL = Counter(
    "rose_blanche_upload_requests_total",
    "Total number of file upload requests",
    ["status"],  # success / error
)

UPLOAD_FILES_TOTAL = Counter(
    "rose_blanche_upload_files_total",
    "Total number of files uploaded",
    ["status"],  # success / skipped / error
)

# ── Ingestion metrics ────────────────────────────────────────────
INGESTION_RUNS_TOTAL = Counter(
    "rose_blanche_ingestion_runs_total",
    "Total ingestion/reingestion runs",
    ["type", "status"],  # type: ingest/reingest, status: success/error
)

INGESTION_DOCUMENTS_TOTAL = Gauge(
    "rose_blanche_ingestion_documents_total",
    "Total number of documents ingested",
)

INGESTION_FRAGMENTS_TOTAL = Gauge(
    "rose_blanche_ingestion_fragments_total",
    "Total number of text fragments (embeddings) stored",
)

INGESTION_DURATION = Histogram(
    "rose_blanche_ingestion_duration_seconds",
    "Duration of ingestion runs in seconds",
    ["type"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

# ── Celery task metrics ──────────────────────────────────────────
CELERY_TASKS_SUBMITTED = Counter(
    "rose_blanche_celery_tasks_submitted_total",
    "Total Celery tasks submitted",
    ["task_name"],
)

CELERY_TASKS_COMPLETED = Counter(
    "rose_blanche_celery_tasks_completed_total",
    "Total Celery tasks completed",
    ["task_name", "status"],  # status: SUCCESS/FAILURE
)

# ── Database metrics ─────────────────────────────────────────────
DB_CONNECTIONS_ACTIVE = Gauge(
    "rose_blanche_db_connections_active",
    "Number of active database connections",
)

EMBEDDINGS_TOTAL = Gauge(
    "rose_blanche_embeddings_total",
    "Total embeddings stored in pgvector",
)
