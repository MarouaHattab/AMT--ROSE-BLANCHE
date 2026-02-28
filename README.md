<p align="center">
  <img src="demo/logo.png" alt="Rose Blanche Logo" width="160"/>
</p>

<h1 align="center">🌹 Rose Blanche — RAG Semantic Search API</h1>

<p align="center">
  <strong>Défi AMT — Bakery & Pastry Formulation Assistant</strong><br/>
  Retrieval-Augmented Generation module for intelligent enzyme dosage retrieval
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-17-336791?logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/pgvector-0.3-4169E1" alt="pgvector"/>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white" alt="Celery"/>
  <img src="https://img.shields.io/badge/RabbitMQ-3.13-FF6600?logo=rabbitmq&logoColor=white" alt="RabbitMQ"/>
  <img src="https://img.shields.io/badge/Flower-Monitoring-green" alt="Flower"/>
  <img src="https://img.shields.io/badge/Grafana-11.1-F46800?logo=grafana&logoColor=white" alt="Grafana"/>
  <img src="https://img.shields.io/badge/Prometheus-2.53-E6522C?logo=prometheus&logoColor=white" alt="Prometheus"/>
  <img src="https://img.shields.io/badge/Model-MiniLM--L6--v2-orange" alt="Model"/>
</p>

---

## 📖 About

**Rose Blanche RAG API** is a semantic search engine built for the **AMT (Agro-Mediterranean Technologies)** challenge. It helps bakery and pastry professionals find recommended enzyme dosages, product specifications, and formulation guidance from **BVZyme** technical data sheets.

The system ingests **35 technical data sheets** (TDS) covering bakery enzymes (alpha-amylase, xylanase, lipase, transglutaminase, glucose oxidase, amyloglucosidase, maltogenic amylase) and ascorbic acid, then answers formulation questions via **cosine similarity** search on dense vector embeddings.

### Challenge Question

> _"Quelles sont les quantités recommandées d'acide ascorbique, d'alpha-amylase et de xylanase pour l'amélioration de la panification ?"_

### Search Test Results

<p align="center">
  <img src="demo/test.png" alt="Search Test Result" width="800"/>
</p>

<p align="center">
  <img src="demo/test2.png" alt="Search Test Result 2" width="800"/>
</p>

---

## 🎬 Demo

<p align="center">
  <img src="demo/demo.gif" alt="Demo GIF" width="800"/>
</p>

🔗 **Prototype Video:** [Watch on Google Drive](https://drive.google.com/file/d/1JDMiMOWQVA3z_bxoHZuHhGh9LbLgWBqz/view?usp=sharing)

---

## 🏗️ Architecture

The system follows a **layered microservices architecture** orchestrated with Docker Compose. At its core, the **FastAPI application** serves as the central hub — handling HTTP requests, coordinating with the embedding model, and querying the vector database. The architecture is divided into five major layers:

1. **Client Layer** — Web UI, Postman, and monitoring dashboards (Flower, Grafana) communicate with the API over REST.
2. **API Layer** — FastAPI handles routing, middleware (CORS, Prometheus instrumentation), and delegates work to controllers. The **DataController** manages ingestion (read → chunk → embed → store) while the **SearchController** handles semantic search (query expansion → embedding → cosine similarity → RRF fusion).
3. **Async Processing Layer** — Heavy tasks (ingestion, re-ingestion) are offloaded to **Celery workers** via **RabbitMQ**. **Celery Beat** schedules periodic jobs (health checks every 5 min, full re-ingestion daily). **Flower** provides real-time worker monitoring.
4. **Data Layer** — **PostgreSQL 17 + pgvector** stores documents and their 384-dimensional embeddings. Cosine similarity search is performed directly in SQL via pgvector operators.
5. **Observability Layer** — **Prometheus** scrapes the `/metrics` endpoint every 15s, collecting search quality metrics (cosine scores, ingredient coverage, latency percentiles). **Grafana** visualizes these metrics through a pre-provisioned 23-panel dashboard.

```mermaid
flowchart TB
    subgraph CLIENT["🖥️ Client"]
        UI["Web UI<br/>(Static HTML + Tailwind)"]
        PM["Postman / cURL"]
        FL["Flower Dashboard<br/>:5555"]
        GF["Grafana Dashboard<br/>:3000"]
    end

    subgraph API["⚙️ FastAPI Application"]
        direction TB
        MW["CORS Middleware"]
        RT["Router Layer"]

        subgraph ROUTES["Routes"]
            R1["GET /api/v1/<br/>Health Check"]
            R2["POST /api/v1/data/ingest<br/>Sync Ingestion"]
            R3["POST /api/v1/data/reingest<br/>Sync Re-ingestion"]
            R4["GET /api/v1/data/documents<br/>List Documents"]
            R5["GET /api/v1/data/embeddings/count<br/>Embeddings Count"]
            R6["POST /api/v1/search/<br/>Semantic Search"]
            R7["GET /api/v1/search/stats<br/>Search Stats"]
            R8["POST /api/v1/tasks/ingest<br/>Async Ingest"]
            R9["POST /api/v1/tasks/reingest<br/>Async Re-ingest"]
            R10["GET /api/v1/tasks/{id}<br/>Poll Task Status"]
        end

        subgraph CTRL["Controllers"]
            DC["DataController<br/>• Read .md files<br/>• Extract structured info<br/>• Smart chunking<br/>• Bilingual enrichment"]
            SC["SearchController<br/>• Query expansion (FR↔EN)<br/>• Ingredient detection<br/>• Multi-query decomposition<br/>• Score fusion (RRF)"]
        end

        subgraph STORES["Stores"]
            ES["EmbeddingService<br/>sentence-transformers<br/>all-MiniLM-L6-v2 (384D)"]
            VS["PGVectorProvider<br/>Cosine similarity search"]
        end
    end

    subgraph ASYNC["🔄 Asynchronous Processing"]
        RMQ["RabbitMQ<br/>Message Broker<br/>:5672 / :15672"]
        CW["Celery Worker<br/>Background Tasks<br/>(concurrency=2)"]
        CB["Celery Beat<br/>Task Scheduler<br/>(periodic jobs)"]
        FW["Flower<br/>Monitoring UI<br/>:5555"]
    end

    subgraph MONITORING["📊 Observability Stack"]
        PROM["Prometheus<br/>Metrics Collection<br/>:9090"]
        GRAF["Grafana<br/>Dashboards & Alerts<br/>:3000"]
    end

    subgraph DB["🗄️ PostgreSQL + pgvector"]
        T1["documents<br/>(id, filename, title, ...)"]
        T2["embeddings<br/>(id, doc_id, text, vector(384))"]
    end

    subgraph DATA["📁 Dataset (35 TDS)"]
        MD["Markdown Files<br/>Converted from PDF"]
        GD["Google Drive Source<br/>(Original PDFs)"]
    end

    UI & PM --> MW --> RT --> ROUTES
    R2 & R3 --> DC
    R6 --> SC
    R8 & R9 -->|"send_task()"| RMQ
    RMQ --> CW
    CB -->|"scheduled tasks"| RMQ
    CW --> DC
    CW --> ES
    CW --> T1 & T2
    DC --> ES --> T2
    DC --> T1
    SC --> ES
    SC --> VS --> T2
    FL --> FW
    FW --> RMQ
    GF --> GRAF
    PROM -->|"scrape /metrics"| MW
    GRAF -->|"query"| PROM
    GD -.->|"PDF → Markdown"| MD
    MD -->|"Auto-ingest on startup"| DC

    style CLIENT fill:#fef3c7,stroke:#f59e0b,color:#000
    style API fill:#dbeafe,stroke:#3b82f6,color:#000
    style ASYNC fill:#fef9c3,stroke:#eab308,color:#000
    style MONITORING fill:#fde68a,stroke:#f59e0b,color:#000
    style DB fill:#d1fae5,stroke:#10b981,color:#000
    style DATA fill:#fce7f3,stroke:#ec4899,color:#000
    style ROUTES fill:#e0e7ff,stroke:#6366f1,color:#000
    style CTRL fill:#e0e7ff,stroke:#6366f1,color:#000
    style STORES fill:#e0e7ff,stroke:#6366f1,color:#000
```

### Data Flow — Semantic Search

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant SC as SearchController
    participant ES as EmbeddingService
    participant PG as PostgreSQL + pgvector

    U->>API: POST /api/v1/search/<br/>{"question": "...", "top_k": 3}
    API->>SC: search(question, top_k)

    Note over SC: 1. Detect ingredients in query
    Note over SC: 2. Expand query (FR↔EN bilingual)
    Note over SC: 3. Generate sub-queries per ingredient

    SC->>ES: encode(expanded_queries)
    ES-->>SC: embedding vectors (384D)

    SC->>PG: cosine similarity search
    PG-->>SC: top-K fragments per sub-query

    Note over SC: 4. Reciprocal Rank Fusion (RRF)
    Note over SC: 5. Compute coverage metrics

    SC-->>API: ranked results + metrics
    API-->>U: JSON response
```

### Data Flow — Async Ingestion (Celery)

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant RMQ as RabbitMQ
    participant CW as Celery Worker
    participant ES as EmbeddingService
    participant PG as PostgreSQL

    U->>API: POST /api/v1/tasks/ingest
    API->>RMQ: send_task(ingest_documents)
    API-->>U: 202 Accepted {task_id}

    RMQ->>CW: deliver task
    CW->>CW: update state → PROGRESS
    CW->>ES: load model + encode chunks
    CW->>PG: store embeddings
    CW->>CW: update state → SUCCESS

    U->>API: GET /api/v1/tasks/{task_id}
    API->>RMQ: AsyncResult(task_id)
    API-->>U: {status: SUCCESS, result: {...}}
```

---

## 📊 Technical Specifications

| Parameter              | Value                                 |
| ---------------------- | ------------------------------------- |
| **Embedding Model**    | `all-MiniLM-L6-v2`                    |
| **Library**            | `sentence-transformers`               |
| **Vector Dimension**   | 384                                   |
| **Similarity Metric**  | Cosine Similarity                     |
| **Default Top-K**      | 3                                     |
| **Database**           | PostgreSQL 17 + pgvector              |
| **Chunking**           | Smart structured extraction + overlap |
| **Default Chunk Size** | 500 characters                        |
| **Default Overlap**    | 50 characters                         |
| **Query Expansion**    | French ↔ English bilingual            |
| **Score Fusion**       | Reciprocal Rank Fusion (RRF)          |
| **Task Queue**         | Celery 5.4                            |
| **Message Broker**     | RabbitMQ 3.13                         |
| **Task Scheduler**     | Celery Beat                           |
| **Task Monitoring**    | Flower                                |
| **Metrics Collection** | Prometheus 2.53                       |
| **Dashboards**         | Grafana 11.1                          |

---

## 📁 Dataset

The dataset consists of **35 Technical Data Sheets (TDS)** from **BVZyme** enzyme products, originally in PDF format.

🔗 **Original Source:** [Google Drive — BVZyme TDS Collection](https://drive.google.com/drive/folders/10nR80LKvyVeTyE8qD8bBi1MPdgvmvLMJ)

The PDFs were converted to **Markdown** for structured extraction and are stored in the [`dataset/`](dataset/) folder.

### Covered Products

| Enzyme Type                | Products                              | Dosage Range |
| -------------------------- | ------------------------------------- | ------------ |
| **Ascorbic Acid** (E300)   | Acide Ascorbique                      | 20–300 ppm   |
| **Alpha-Amylase** (Fungal) | AF110, AF220, AF330, AF SX            | 2–25 ppm     |
| **Maltogenic Amylase**     | A FRESH101/202/303, A SOFT205/305/405 | 10–100 ppm   |
| **Glucose Oxidase**        | GOX 110, GO MAX 63/65                 | 5–50 ppm     |
| **Lipase**                 | L MAX X/63/64/65, L55, L65            | 2–60 ppm     |
| **Transglutaminase**       | TG881, TG883, TG MAX63/64             | 5–40 ppm     |
| **Xylanase** (Bacterial)   | HCB708, HCB709, HCB710                | 5–30 ppm     |
| **Xylanase** (Fungal)      | HCF400/500/600, HCF MAX X/63/64       | 0.5–70 ppm   |
| **Amyloglucosidase**       | AMG880, AMG1400                       | 10–100 ppm   |

---

## 🐳 Docker Deployment

The entire stack runs with a single command using Docker Compose.

### Docker Containers

<p align="center">
  <img src="demo/docker/docker.png" alt="Docker Containers" width="800"/>
</p>

### Quick Start

```bash
# Clone the repository
git clone https://github.com/MarouaHattab/AMT--ROSE-BLANCHE.git
cd AMT--ROSE-BLANCHE

# Start all services (PostgreSQL + API)
cd rose-blanche-api
docker compose up --build -d
```

The API will be available at **http://localhost:8000** and the dataset is **automatically ingested on startup**.

### Services

| Container                    | Image                      | Port         | Description                            |
| ---------------------------- | -------------------------- | ------------ | -------------------------------------- |
| `rose-blanche-db`            | `pgvector/pgvector:pg17`   | 5432         | PostgreSQL with pgvector extension     |
| `rose-blanche-api`           | Custom (Python 3.11)       | 8000         | FastAPI backend + embedded model       |
| `rose-blanche-rabbitmq`      | `rabbitmq:3.13-management` | 5672 / 15672 | Message broker (AMQP + Management UI)  |
| `rose-blanche-celery-worker` | Custom (Python 3.11)       | —            | Background task worker (concurrency=2) |
| `rose-blanche-celery-beat`   | Custom (Python 3.11)       | —            | Periodic task scheduler                |
| `rose-blanche-flower`        | Custom (Python 3.11)       | 5555         | Celery monitoring dashboard            |
| `rose-blanche-prometheus`    | `prom/prometheus:v2.53.0`  | 9090         | Metrics collection & storage (30d)     |
| `rose-blanche-grafana`       | `grafana/grafana:11.1.0`   | 3000         | Production dashboards & alerts         |

### Environment Variables

| Variable                    | Default                              | Description                         |
| --------------------------- | ------------------------------------ | ----------------------------------- |
| `POSTGRES_USERNAME`         | `postgres`                           | Database username                   |
| `POSTGRES_PASSWORD`         | `admin`                              | Database password                   |
| `POSTGRES_HOST`             | `postgres`                           | Database host (Docker service name) |
| `POSTGRES_PORT`             | `5432`                               | Database port                       |
| `POSTGRES_MAIN_DATABASE`    | `rose_blanche`                       | Database name                       |
| `EMBEDDING_MODEL_ID`        | `all-MiniLM-L6-v2`                   | Sentence-transformers model         |
| `EMBEDDING_MODEL_SIZE`      | `384`                                | Embedding vector dimension          |
| `VECTOR_DB_DISTANCE_METHOD` | `cosine`                             | Similarity metric                   |
| `DEFAULT_CHUNK_SIZE`        | `500`                                | Text chunk size (characters)        |
| `DEFAULT_OVERLAP_SIZE`      | `50`                                 | Overlap between chunks              |
| `DEFAULT_TOP_K`             | `3`                                  | Default number of results           |
| `AUTO_INGEST`               | `true`                               | Auto-ingest dataset on startup      |
| `CELERY_BROKER_URL`         | `amqp://guest:guest@rabbitmq:5672//` | RabbitMQ connection URL             |
| `CELERY_RESULT_BACKEND`     | `rpc://`                             | Celery result backend               |

---

## 🔌 API Endpoints

### Health Check

```http
GET /api/v1/
```

Returns API metadata (app name, version, model info, top_k).

### Data Ingestion

```http
POST /api/v1/data/ingest
Content-Type: application/json

{
  "chunk_size": 500,
  "overlap_size": 50
}
```

Reads all `.md` files from the dataset directory, chunks them, generates embeddings, and stores them in PostgreSQL.

### Re-Ingest (Full Reset)

```http
POST /api/v1/data/reingest
Content-Type: application/json

{}
```

Drops all existing data and re-ingests from scratch.

### List Documents

```http
GET /api/v1/data/documents
```

Returns all ingested documents with metadata.

### Embeddings Count

```http
GET /api/v1/data/embeddings/count
```

### Semantic Search (Main Endpoint)

```http
POST /api/v1/search/
Content-Type: application/json

{
  "question": "Quelles sont les quantités recommandées d'acide ascorbique, d'alpha-amylase et de xylanase pour l'amélioration de la panification ?",
  "top_k": 3
}
```

**Response:**

```json
{
  "signal": "search_success",
  "question": "...",
  "top_k": 3,
  "results": [
    { "rank": 1, "text": "...", "score": 0.91, "document_id": 1 },
    { "rank": 2, "text": "...", "score": 0.87, "document_id": 2 },
    { "rank": 3, "text": "...", "score": 0.82, "document_id": 3 }
  ],
  "metrics": {
    "average_score": 0.8667,
    "min_score": 0.82,
    "max_score": 0.91,
    "unique_documents": 3,
    "total_results": 3,
    "detected_ingredients": ["ascorbic acid", "alpha-amylase", "xylanase"],
    "ingredient_coverage": 1.0,
    "coverage_detail": "3/3 ingredients found in results"
  }
}
```

### Search Stats

```http
GET /api/v1/search/stats
```

### Async Ingestion (Celery)

```http
POST /api/v1/tasks/ingest
Content-Type: application/json

{
  "chunk_size": 500,
  "overlap_size": 50
}
```

Returns `202 Accepted` with a `task_id` to poll for progress.

### Async Re-Ingest (Celery)

```http
POST /api/v1/tasks/reingest
Content-Type: application/json

{}
```

### Poll Task Status

```http
GET /api/v1/tasks/{task_id}
```

**Response:**

```json
{
  "task_id": "a1b2c3d4-...",
  "status": "SUCCESS",
  "result": {
    "status": "COMPLETED",
    "total_documents": 35,
    "total_fragments": 420
  }
}
```

### Revoke (Cancel) Task

```http
DELETE /api/v1/tasks/{task_id}
```

### List Active Tasks

```http
GET /api/v1/tasks/
```

### Monitoring Dashboards

| Dashboard      | URL                        | Credentials         | Description                                         |
| -------------- | -------------------------- | ------------------- | --------------------------------------------------- |
| **Grafana**    | http://localhost:3000      | admin / roseblanche | Production evaluation metrics & dashboards          |
| **Prometheus** | http://localhost:9090      | —                   | Raw metrics, PromQL queries, target health          |
| **Flower**     | http://localhost:5555      | —                   | Celery task monitoring, worker status, task history |
| **RabbitMQ**   | http://localhost:15672     | guest / guest       | Message broker management                           |
| **Swagger**    | http://localhost:8000/docs | —                   | Interactive API documentation                       |

### Flower — Celery Monitoring

<p align="center">
  <img src="demo/flower/flower.png" alt="Flower Dashboard" width="800"/>
</p>

<p align="center">
  <img src="demo/flower/flower-in-details.png" alt="Flower Task Details" width="800"/>
</p>

### RabbitMQ Management

<p align="center">
  <img src="demo/rabbit-mq/overview.png" alt="RabbitMQ Overview" width="800"/>
</p>

<p align="center">
  <img src="demo/rabbit-mq/queues.png" alt="RabbitMQ Queues" width="800"/>
</p>

### Prometheus Targets

<p align="center">
  <img src="demo/prometheus/prometheus .png" alt="Prometheus Targets" width="800"/>
</p>

### FastAPI — Swagger UI

<p align="center">
  <img src="demo/fastapi.png" alt="FastAPI Swagger UI" width="800"/>
</p>

---

## 📊 Grafana — Production Evaluation Metrics

Grafana provides a pre-configured production dashboard for monitoring RAG search quality, system performance, and data pipeline health.

### Access

- **URL:** http://localhost:3000
- **Username:** `admin`
- **Password:** `roseblanche`

### Dashboard: Rose Blanche — RAG Evaluation Metrics

The dashboard is **auto-provisioned** on startup and contains 4 sections with 23 panels:

#### 🌹 Overview (KPI Cards)

| Panel                   | Metric                               | Threshold Colors                 |
| ----------------------- | ------------------------------------ | -------------------------------- |
| Total Search Requests   | `rose_blanche_search_requests_total` | Red → Yellow → Green             |
| Search Success Rate     | Success / Total ratio                | Red < 50% → Orange → Green > 80% |
| Avg Cosine Score        | Mean similarity score                | Red < 0.4 → Yellow → Green > 0.8 |
| Avg Ingredient Coverage | Median ingredient coverage           | Red < 50% → Green > 50%          |
| P95 Search Latency      | 95th percentile latency              | Green < 0.5s → Yellow → Red > 2s |
| Total Embeddings        | `rose_blanche_embeddings_total`      | Blue                             |

#### 🔍 Search Quality Metrics

| Panel                            | Description                                                |
| -------------------------------- | ---------------------------------------------------------- |
| Cosine Score Distribution        | P50/P75/P90/P99 percentiles of cosine similarity over time |
| Ingredient Coverage Distribution | Median and P90 coverage ratio over time                    |
| Ingredients Detected vs Covered  | Per-ingredient detection and coverage rates (stacked bars) |
| Average Score Per Search         | Running average of search quality                          |

#### ⚡ Performance & Latency

| Panel                         | Description                                 |
| ----------------------------- | ------------------------------------------- |
| Search Latency Percentiles    | P50/P90/P95/P99 latency over time           |
| Request Rate (req/s)          | Overall and per-status search request rates |
| HTTP Duration by Endpoint     | P95 latency per API endpoint                |
| HTTP Responses by Status Code | 2xx/4xx/5xx response distribution           |

#### 📥 Ingestion & Data Pipeline

| Panel                          | Description                                     |
| ------------------------------ | ----------------------------------------------- |
| Documents Ingested             | Current total documents                         |
| Total Fragments                | Current total text fragments (embeddings)       |
| Ingestion Runs (Success/Error) | Counter of successful and failed ingestion runs |
| Ingestion Duration             | P50/P95 ingestion time                          |
| Celery Tasks                   | Submitted vs completed tasks by name and status |

#### 🏥 System Health

| Panel                 | Description                                     |
| --------------------- | ----------------------------------------------- |
| API Status            | UP/DOWN indicator from Prometheus target scrape |
| Process Memory Usage  | RSS and virtual memory of the FastAPI process   |
| Open File Descriptors | Current vs max file descriptor usage            |

### Prometheus Metrics Endpoint

The API exposes metrics at **GET /metrics** (Prometheus format). Key custom metrics:

```
# Search quality
rose_blanche_search_requests_total{status="success|no_results|error"}
rose_blanche_cosine_score_bucket{le="0.1|...|1.0"}
rose_blanche_search_avg_score_sum / _count
rose_blanche_ingredient_coverage_bucket{le="0.0|...|1.0"}
rose_blanche_ingredients_detected_total{ingredient="..."}
rose_blanche_ingredients_covered_total{ingredient="..."}

# Performance
rose_blanche_search_latency_seconds_bucket{le="0.05|...|10.0"}
rose_blanche_search_top_k_bucket
rose_blanche_search_results_count_bucket

# Ingestion
rose_blanche_ingestion_runs_total{type="ingest|reingest", status="success|error"}
rose_blanche_ingestion_documents_total
rose_blanche_ingestion_fragments_total
rose_blanche_ingestion_duration_seconds_bucket

# Celery
rose_blanche_celery_tasks_submitted_total{task_name="..."}
rose_blanche_celery_tasks_completed_total{task_name="...", status="SUCCESS|FAILURE"}
```

### Grafana Dashboard Screenshot

<p align="center">
  <img src="demo/Grafana/grafana.png" alt="Grafana Dashboard" width="800"/>
</p>

---

## 🧪 Postman Tests

A complete Postman collection is provided to test all API endpoints.

### Import the Collection

1. Open **Postman**
2. Click **Import** → select [`postman/Rose-Blanche-RAG-API.postman_collection.json`](rose-blanche-api/postman/Rose-Blanche-RAG-API.postman_collection.json)
3. The collection variable `{{base_url}}` defaults to `http://localhost:8000`

### Test Coverage

| Folder                   | Tests | Description                                                       |
| ------------------------ | ----- | ----------------------------------------------------------------- |
| **Health & Info**        | 1     | Welcome endpoint, model validation                                |
| **Data Ingestion**       | 5     | Ingest, re-ingest, list docs, embeddings count                    |
| **Semantic Search**      | 8     | Challenge questions (FR/EN), single ingredients, multi-ingredient |
| **Search Statistics**    | 1     | Model info, dimension, similarity method                          |
| **Async Tasks (Celery)** | 5     | Submit ingest, re-ingest, poll status, revoke, list active        |

### Test Captures

<p align="center">
  <img src="demo/postman/postman-test.png" alt="Postman Test Results" width="800"/>
</p>

Each test request includes **automated assertions** that verify:

- ✅ HTTP status codes (200)
- ✅ Response signal values (`search_success`, `ingestion_success`)
- ✅ Result count matches `top_k`
- ✅ Relevance scores above threshold
- ✅ Ingredient detection and coverage
- ✅ Correct model and dimension metadata

---

## 📂 Project Structure

```
.
├── dataset/                          # 35 Markdown TDS files (converted from PDF)
│   ├── acide ascorbique.md
│   ├── BVZyme TDS AF110.md
│   ├── BVZyme TDS A FRESH101.md
│   ├── TDS BVzyme HCF MAX63.md
│   └── ... (35 files total)
│
├── demo/                             # Demo assets
│   ├── demo.gif                      # Application demo recording
│   ├── logo.png                      # Project logo
│   ├── fastapi.png                   # FastAPI Swagger UI screenshot
│   ├── test.png                      # Search test result screenshot
│   ├── test2.png                     # Additional test screenshot
│   ├── docker/
│   │   └── docker.png                # Docker containers screenshot
│   ├── flower/
│   │   ├── flower.png                # Flower overview screenshot
│   │   └── flower-in-details.png     # Flower task details screenshot
│   ├── Grafana/
│   │   └── grafana.png               # Grafana dashboard screenshot
│   ├── prometheus/
│   │   └── prometheus .png           # Prometheus targets screenshot
│   ├── rabbit-mq/
│   │   ├── overview.png              # RabbitMQ overview screenshot
│   │   └── queues.png                # RabbitMQ queues screenshot
│   └── postman/
│       └── postman-test.png          # Postman test results screenshot
│
├── rose-blanche-api/                 # FastAPI application
│   ├── main.py                       # App entry point + startup/shutdown
│   ├── Dockerfile                    # Multi-stage Docker build
│   ├── docker-compose.yml            # PostgreSQL + API stack
│   ├── requirements.txt              # Python dependencies
│   │
│   ├── controllers/
│   │   ├── BaseController.py         # Base controller class
│   │   ├── DataController.py         # Ingestion: read MD → chunk → embed → store
│   │   └── SearchController.py       # Search: query expansion → embed → cosine → RRF
│   │
│   ├── helpers/
│   │   ├── config.py                 # Pydantic settings (env-based config)
│   │   └── metrics.py                # Prometheus custom metrics definitions
│   │
│   ├── models/
│   │   ├── BaseDataModel.py          # Base async model
│   │   ├── DocumentModel.py          # CRUD for documents table
│   │   ├── EmbeddingModel.py         # CRUD for embeddings table
│   │   ├── db_schemes/
│   │   │   ├── base.py               # SQLAlchemy declarative base
│   │   │   └── schemes.py            # Document, Embedding, RetrievedFragment
│   │   └── enums/
│   │       └── ResponseEnums.py      # API response signals
│   │
│   ├── celery_app.py                 # Celery configuration + Beat schedule
│   │
│   ├── tasks/
│   │   └── ingestion_tasks.py        # Background tasks: ingest, reingest, health
│   │
│   ├── routes/
│   │   ├── base.py                   # GET /api/v1/
│   │   ├── data.py                   # POST ingest, GET documents
│   │   ├── search.py                 # POST search/, GET stats
│   │   ├── tasks.py                  # POST async ingest/reingest, GET status
│   │   └── schemes/
│   │       └── search.py             # Pydantic request models
│   │
│   ├── stores/
│   │   ├── embedding/
│   │   │   └── EmbeddingService.py   # sentence-transformers wrapper
│   │   └── vectordb/
│   │       ├── PGVectorProvider.py   # pgvector cosine search
│   │       └── VectorDBEnums.py      # Distance method enums
│   │
│   ├── static/
│   │   └── index.html                # Web UI (Tailwind CSS)
│   │
│   ├── postman/
│   │   └── Rose-Blanche-RAG-API.postman_collection.json
│   │
│   ├── monitoring/
│   │   ├── prometheus/
│   │   │   └── prometheus.yml        # Prometheus scrape configuration
│   │   └── grafana/
│   │       ├── provisioning/
│   │       │   ├── datasources/
│   │       │   │   └── datasource.yml  # Prometheus datasource (auto-provisioned)
│   │       │   └── dashboards/
│   │       │       └── dashboard.yml   # Dashboard provider config
│   │       └── dashboards/
│   │           └── rose-blanche-dashboard.json  # Pre-built Grafana dashboard
│   │
│   └── tests/
│       └── test_search_accuracy.py   # Automated accuracy tests
│
└── README.md                         # This file
```

---

## ⚙️ Local Development (Without Docker)

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 2. Install dependencies
cd rose-blanche-api
pip install -r requirements.txt

# 3. Start PostgreSQL with pgvector
# Make sure PostgreSQL is running with the pgvector extension installed

# 4. Configure environment
# Create a .env file or set environment variables (see table above)

# 5. Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** to access the Web UI, or **http://localhost:8000/docs** for the interactive Swagger documentation.

---

## 🔍 How It Works

### 1. Data Ingestion Pipeline

```
PDF (Google Drive) → Markdown → Structured Extraction → Smart Chunking → Embedding → pgvector
```

- **Structured extraction** pulls product name, enzyme type, activity, dosage, application, storage info
- **Bilingual enrichment** adds French ↔ English synonyms to improve cross-language retrieval
- **Smart chunking** creates semantic chunks with configurable size and overlap
- **Async mode** — ingestion can run as a background Celery task via `/api/v1/tasks/ingest`

### 2. Search Pipeline

```
User Question → Ingredient Detection → Query Expansion (FR↔EN) → Multi-Query Decomposition → Embedding → Cosine Similarity → RRF Fusion → Ranked Results
```

- **Ingredient detection** identifies known enzymes in the query
- **Query expansion** translates bakery terms between French and English
- **Multi-query decomposition** generates specialized sub-queries per detected ingredient
- **Reciprocal Rank Fusion** merges results from multiple sub-queries
- **Coverage metrics** report how many detected ingredients appear in results

### 3. Asynchronous Processing (Celery)

```
FastAPI ───send_task()───▶ RabbitMQ ───deliver───▶ Celery Worker ───▶ PostgreSQL
  ▲                                                      │
  │                                                      │
  └───────── poll GET /tasks/{id} ◀────────────────result┘
```

| Component       | Role                                                                         |
| --------------- | ---------------------------------------------------------------------------- |
| **Celery**      | Executes heavy ingestion/embedding tasks in background workers               |
| **RabbitMQ**    | Message broker — reliable task queue with AMQP protocol                      |
| **Celery Beat** | Scheduler — triggers periodic re-ingestion (daily) and health checks (5 min) |
| **Flower**      | Real-time monitoring dashboard for workers, tasks, and queues                |

**Scheduled Tasks (Celery Beat):**

| Task                 | Interval        | Description                      |
| -------------------- | --------------- | -------------------------------- |
| `health_check`       | Every 5 minutes | Verifies database connectivity   |
| `scheduled_reingest` | Every 24 hours  | Full re-ingestion of the dataset |

### 4. Observability & Monitoring

```
FastAPI ──── /metrics ────▶ Prometheus ────▶ Grafana Dashboards
                              (scrape 15s)     (auto-provisioned)
```

The observability stack ensures production readiness through continuous metric collection and visualization:

- **Prometheus Instrumentation** — The FastAPI app is instrumented with `prometheus-fastapi-instrumentator` and custom metrics defined in `helpers/metrics.py`. Every search request records cosine scores, latency, ingredient coverage, and result counts.
- **Prometheus Server** — Scrapes the `/metrics` endpoint every 15 seconds and stores time-series data with 30-day retention.
- **Grafana Dashboard** — A 23-panel dashboard is auto-provisioned on startup, organized into 4 sections: Overview KPIs, Search Quality, Performance & Latency, and Ingestion Pipeline. No manual setup required.
- **Custom Metrics** — Beyond standard HTTP metrics, the system tracks domain-specific evaluation metrics: cosine similarity distribution, ingredient detection/coverage rates, search success ratio, and ingestion run durations.

---

## 📜 License

This project was developed for the **AMT — Rose Blanche** During AI NIGHT challenge 2K26.

