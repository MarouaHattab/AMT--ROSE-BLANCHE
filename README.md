<p align="center">
  <img src="demo/banner.png" alt="Rose Blanche Banner" width="100%"/>
</p>

<h1 align="center">🌹 Rose Blanche — RAG Semantic Search API</h1>

<p align="center">
  <strong>Défi AMT — Bakery & Pastry Formulation Assistant</strong><br/>
  An intelligent Retrieval-Augmented Generation engine for enzyme dosage retrieval, built for the AI Night 2K26 challenge.
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

## 📑 Table of Contents

- [About the Project](#-about-the-project)
- [The Challenge](#-the-challenge)
- [Evaluation & Results](#-evaluation--results)
- [Demo](#-demo)
- [Architecture](#%EF%B8%8F-architecture)
- [Technical Specifications](#-technical-specifications)
- [Dataset](#-dataset)
- [Getting Started](#-getting-started)
- [API Reference](#-api-reference)
- [Monitoring & Observability](#-monitoring--observability)
- [Postman Tests](#-postman-tests)
- [Project Structure](#-project-structure)
- [How It Works](#-how-it-works)
- [License](#-license)

---

## 📖 About the Project

**Rose Blanche** is a production-grade **Retrieval-Augmented Generation (RAG)** semantic search API built for the **AMT (Agro-Mediterranean Technologies) — AI Night 2K26** challenge.

The problem it solves is simple but critical: bakery and pastry professionals need quick, accurate answers about enzyme dosages, product specifications, and formulation guidance — information that is scattered across dozens of PDF technical data sheets. Manually searching through these documents is slow, error-prone, and impractical on a production floor.

Rose Blanche automates this entirely. It:

1. **Ingests** 35 BVZyme technical data sheets (converted from PDF to Markdown).
2. **Extracts** structured information: product names, enzyme types, activities, dosages, applications, and storage conditions.
3. **Chunks** the text into semantically meaningful fragments with configurable size and overlap.
4. **Embeds** each fragment into a 384-dimensional vector using the `all-MiniLM-L6-v2` sentence-transformer model.
5. **Stores** vectors in PostgreSQL with the `pgvector` extension for native cosine similarity search.
6. **Answers** formulation questions in both French and English via a multi-step search pipeline: ingredient detection → bilingual query expansion → multi-query decomposition → cosine similarity → Reciprocal Rank Fusion (RRF).

The result is a **sub-second, multi-ingredient semantic search** that returns ranked results with quality metrics (cosine scores, ingredient coverage) — all exposed through a clean REST API.

### Key Features

| Feature                         | Description                                                                                           |
| ------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Bilingual Search**            | Queries work in both French and English. Internal translation ensures cross-language retrieval.       |
| **Multi-Ingredient Detection**  | Automatically identifies enzyme names in the query and generates specialized sub-queries for each.    |
| **Reciprocal Rank Fusion**      | Merges results from multiple sub-queries into a single, high-quality ranked list.                     |
| **Ingredient Coverage Metrics** | Each response reports how many detected ingredients are actually represented in the results.          |
| **Async Processing**            | Heavy ingestion tasks run in the background via Celery + RabbitMQ, keeping the API responsive.        |
| **Scheduled Tasks**             | Celery Beat triggers periodic health checks (every 5 min) and full re-ingestion (daily).              |
| **Production Monitoring**       | Prometheus collects custom metrics; Grafana visualizes them in a 23-panel auto-provisioned dashboard. |
| **One-Command Deployment**      | The entire 8-service stack starts with `docker compose up --build -d`.                                |

---

## 🎯 The Challenge

The AMT challenge poses a real-world formulation question:

> _"Quelles sont les quantités recommandées d'acide ascorbique, d'alpha-amylase et de xylanase pour l'amélioration de la panification ?"_
>
> _(What are the recommended quantities of ascorbic acid, alpha-amylase, and xylanase for improving bread-making?)_

This is a **multi-ingredient** question that requires finding dosage information across **three different product categories** — ascorbic acid, alpha-amylase (fungal amylase), and xylanase (bacterial/fungal). Rose Blanche detects all three ingredients, searches the dataset independently for each, and fuses the results into a single ranked response with full coverage metrics.

---

## 📈 Evaluation & Results

To demonstrate the correctness and effectiveness of the search engine, we evaluate Rose Blanche using standard **Information Retrieval (IR)** metrics on a suite of **12 test queries** (multi-ingredient and single-ingredient) with manually curated ground truth.

### Evaluation Metrics

| Metric                           | Definition                                                                                                                                                               |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Recall@3**                     | Proportion of relevant documents (expected ingredients) retrieved in the top 3 results. A Recall@3 of 1.0 means all expected ingredients appear in the returned results. |
| **MRR@3** (Mean Reciprocal Rank) | Average of the reciprocal rank of the **first relevant result** across all queries. MRR@3 = 1.0 means the first result is always relevant.                               |
| **Avg Cosine Score**             | Mean cosine similarity score across all returned results. Higher is better (max = 1.0).                                                                                  |
| **Ingredient Coverage**          | Fraction of detected ingredients that are actually represented in the search results (e.g., "3/3 ingredients found").                                                    |
| **Test Pass Rate**               | Percentage of test cases that meet all thresholds (coverage, score, diversity).                                                                                          |

### Test Suite

The test suite (`tests/test_search_accuracy.py`) contains **12 queries** covering:

| Category                   | Tests            | Description                                                                  |
| -------------------------- | ---------------- | ---------------------------------------------------------------------------- |
| **Multi-ingredient (FR)**  | T01, T03         | Challenge question with 3 ingredients, transglutaminase + glucose oxidase    |
| **Multi-ingredient (EN)**  | T02, T04         | English versions of multi-ingredient queries                                 |
| **Single-ingredient (FR)** | T08              | Ascorbic acid dosage in French                                               |
| **Single-ingredient (EN)** | T05–T07, T09–T12 | Lipase, maltogenic amylase, glucose oxidase, AMG, xylanase, transglutaminase |

### Results

| Test ID | Query                                   | Recall@3 | MRR@3 | Avg Score | Pass |
| ------- | --------------------------------------- | -------- | ----- | --------- | ---- |
| T01     | Challenge question (FR) — 3 ingrédients | 1.0      | 1.0   | ≥ 0.70    | ✅   |
| T02     | Challenge question (EN) — 3 ingredients | 1.0      | 1.0   | ≥ 0.70    | ✅   |
| T03     | Transglutaminase + Glucose oxydase (FR) | 1.0      | 1.0   | ≥ 0.60    | ✅   |
| T04     | Lipase + AMG (EN)                       | 1.0      | 1.0   | ≥ 0.55    | ✅   |
| T05     | Lipase dosage (EN)                      | 1.0      | 1.0   | ≥ 0.55    | ✅   |
| T06     | Anti-staling / shelf life (EN)          | 1.0      | 1.0   | ≥ 0.50    | ✅   |
| T07     | Dough tolerance + fermentation (EN)     | 1.0      | 1.0   | ≥ 0.55    | ✅   |
| T08     | Acide ascorbique dosage (FR)            | 1.0      | 1.0   | ≥ 0.55    | ✅   |
| T09     | Golden crust color (EN)                 | 1.0      | 1.0   | ≥ 0.45    | ✅   |
| T10     | Gluten network strength (EN)            | 1.0      | 1.0   | ≥ 0.50    | ✅   |
| T11     | Xylanase for volume (EN)                | 1.0      | 1.0   | ≥ 0.55    | ✅   |
| T12     | Transglutaminase for texture (EN)       | 1.0      | 1.0   | ≥ 0.55    | ✅   |

### Aggregated Scores

| Metric                      | Value                                                   |
| --------------------------- | ------------------------------------------------------- |
| **Mean Recall@3**           | **1.0** (all expected ingredients found in every query) |
| **MRR@3**                   | **1.0** (first result is always relevant)               |
| **Test Pass Rate**          | **100%** (12/12 tests passed)                           |
| **Global Avg Cosine Score** | **≥ 0.55** across all queries                           |

> **Interpretation:** A Recall@3 of 1.0 means the system consistently retrieves all relevant enzyme information within the top 3 results, even for complex multi-ingredient queries. An MRR@3 of 1.0 confirms that the most relevant result always appears at rank 1, demonstrating the effectiveness of the bilingual query expansion and Reciprocal Rank Fusion strategy.

### Run the Tests

```bash
# Make sure the API is running (docker compose up -d)
cd rose-blanche-api
python tests/test_search_accuracy.py
```

---

## 🎬 Demo

<p align="center">
  <img src="demo/demo.gif" alt="Rose Blanche Demo" width="800"/>
</p>

🔗 **Prototype Video:** [Watch on Google Drive](https://drive.google.com/file/d/1JDMiMOWQVA3z_bxoHZuHhGh9LbLgWBqz/view?usp=sharing)

The demo shows a complete end-to-end workflow: starting the Docker stack, ingesting the dataset, running a semantic search query, and reviewing the results with quality metrics.

---

## 🏗️ Architecture

Rose Blanche follows a **layered microservices architecture** orchestrated with Docker Compose. Eight containers work together to provide a complete RAG pipeline with async processing and production observability.

### Architecture Overview

<p align="center">
  <img src="demo/docker/docker.png" alt="Docker Containers — All 8 Services Running" width="800"/>
</p>
<p align="center"><em>All 8 Docker containers running: PostgreSQL, FastAPI API, RabbitMQ, Celery Worker, Celery Beat, Flower, Prometheus, Grafana</em></p>

### The Five Layers

The architecture is divided into five major layers, each with a clear responsibility:

#### 1. Client Layer

The entry points for interacting with the system. Users can access:

- **Web UI** — A static HTML + Tailwind CSS interface served by FastAPI for quick searches.
- **Swagger UI** — Auto-generated interactive API documentation at `/docs`.
- **Postman** — A pre-built collection with 20 requests and automated test scripts.
- **Monitoring Dashboards** — Flower (Celery), RabbitMQ Management, Prometheus, and Grafana.

#### 2. API Layer (FastAPI)

The central hub that handles all HTTP requests. It includes:

- **CORS Middleware** — Allows cross-origin requests from any domain.
- **Prometheus Instrumentation** — Every request is automatically measured (latency, status codes, endpoint).
- **Router Layer** — Four route modules (`base`, `data`, `search`, `tasks`) with clear separation of concerns.
- **DataController** — Reads Markdown files → extracts structured info → chunks text → generates embeddings → stores in PostgreSQL.
- **SearchController** — Detects ingredients → expands query bilingually → decomposes into sub-queries → runs cosine similarity → fuses results with RRF.
- **EmbeddingService** — Wraps the `sentence-transformers` library to encode text into 384D vectors using `all-MiniLM-L6-v2`.
- **PGVectorProvider** — Executes cosine similarity search directly in PostgreSQL via pgvector operators.

<p align="center">
  <img src="demo/fastapi.png" alt="FastAPI — Swagger UI" width="800"/>
</p>
<p align="center"><em>FastAPI Swagger UI — Interactive API documentation with all endpoints</em></p>

#### 3. Async Processing Layer (Celery + RabbitMQ)

Heavy tasks like data ingestion are offloaded to background workers so the API stays responsive:

- **RabbitMQ 3.13** — AMQP message broker that queues tasks reliably. Accessible at port 5672 (AMQP) and 15672 (Management UI).
- **Celery Worker** — Consumes tasks from RabbitMQ, runs ingestion/embedding in the background with concurrency=2.
- **Celery Beat** — Scheduler that triggers periodic jobs: health check every 5 minutes, full dataset re-ingestion every 24 hours.
- **Flower** — Real-time monitoring dashboard for Celery workers, task history, and queue status.

<p align="center">
  <img src="demo/rabbit-mq/overview.png" alt="RabbitMQ — Management Overview" width="800"/>
</p>
<p align="center"><em>RabbitMQ Management UI — Broker overview with connection and queue metrics</em></p>

<p align="center">
  <img src="demo/rabbit-mq/queues.png" alt="RabbitMQ — Queue Details" width="800"/>
</p>
<p align="center"><em>RabbitMQ Queues — Active task queue with message rates and consumer count</em></p>

<p align="center">
  <img src="demo/flower/flower.png" alt="Flower — Celery Dashboard" width="800"/>
</p>
<p align="center"><em>Flower Dashboard — Celery worker status, active tasks, and task success rates</em></p>

<p align="center">
  <img src="demo/flower/flower-in-details.png" alt="Flower — Task Details" width="800"/>
</p>
<p align="center"><em>Flower Task Details — Individual task execution info, arguments, and runtime</em></p>

#### 4. Data Layer (PostgreSQL + pgvector)

The persistence layer that stores both structured data and vector embeddings:

- **PostgreSQL 17** — Robust relational database for documents and metadata.
- **pgvector Extension** — Adds native vector column type and cosine similarity operators for efficient nearest-neighbor search.
- **Documents Table** — Stores file metadata (filename, title, product name, enzyme type).
- **Embeddings Table** — Stores text fragments and their 384-dimensional vector representations.

#### 5. Observability Layer (Prometheus + Grafana)

Production-grade monitoring for both system health and RAG-specific quality metrics:

- **Prometheus 2.53** — Scrapes the FastAPI `/metrics` endpoint every 15 seconds. Stores time-series data with 30-day retention.
- **Grafana 11.1** — Visualizes all metrics in a pre-provisioned 23-panel dashboard. No manual setup required; the dashboard, datasource, and provider are auto-configured on container startup.

<p align="center">
  <img src="demo/prometheus/prometheus .png" alt="Prometheus — Targets" width="800"/>
</p>
<p align="center"><em>Prometheus Targets — API endpoint scrape status (UP) with 15-second interval</em></p>

<p align="center">
  <img src="demo/Grafana/grafana.png" alt="Grafana — RAG Evaluation Dashboard" width="800"/>
</p>
<p align="center"><em>Grafana Dashboard — 23 panels covering search quality, latency, ingestion, and system health</em></p>

### Architecture Diagram

```mermaid
flowchart TB
    subgraph CLIENT["🖥️ Client Layer"]
        UI["Web UI<br/>(Static HTML + Tailwind)"]
        PM["Postman / cURL"]
        FL["Flower Dashboard<br/>:5555"]
        GF["Grafana Dashboard<br/>:3000"]
    end

    subgraph API["⚙️ FastAPI Application — API Layer"]
        direction TB
        MW["CORS + Prometheus Middleware"]
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

    subgraph ASYNC["🔄 Async Processing Layer"]
        RMQ["RabbitMQ<br/>Message Broker<br/>:5672 / :15672"]
        CW["Celery Worker<br/>Background Tasks<br/>(concurrency=2)"]
        CB["Celery Beat<br/>Task Scheduler<br/>(periodic jobs)"]
        FW["Flower<br/>Monitoring UI<br/>:5555"]
    end

    subgraph MONITORING["📊 Observability Layer"]
        PROM["Prometheus<br/>Metrics Collection<br/>:9090"]
        GRAF["Grafana<br/>Dashboards & Alerts<br/>:3000"]
    end

    subgraph DB["🗄️ Data Layer — PostgreSQL + pgvector"]
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

The diagram below shows what happens when a user submits a search query:

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
    API-->>U: JSON response with scores & coverage
```

### Data Flow — Async Ingestion (Celery)

The diagram below shows the asynchronous ingestion flow using Celery and RabbitMQ:

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

| Parameter              | Value                                                  |
| ---------------------- | ------------------------------------------------------ |
| **Embedding Model**    | `all-MiniLM-L6-v2` (sentence-transformers)             |
| **Vector Dimension**   | 384                                                    |
| **Similarity Metric**  | Cosine Similarity                                      |
| **Default Top-K**      | 3                                                      |
| **Database**           | PostgreSQL 17 + pgvector                               |
| **Chunking Strategy**  | Smart structured extraction + overlap                  |
| **Default Chunk Size** | 500 characters                                         |
| **Default Overlap**    | 50 characters                                          |
| **Query Expansion**    | French ↔ English bilingual                             |
| **Score Fusion**       | Reciprocal Rank Fusion (RRF)                           |
| **Task Queue**         | Celery 5.4 + RabbitMQ 3.13                             |
| **Task Scheduler**     | Celery Beat                                            |
| **Task Monitoring**    | Flower 2.0                                             |
| **Metrics Collection** | Prometheus 2.53 (scrape interval: 15s, retention: 30d) |
| **Dashboards**         | Grafana 11.1 (23 panels, auto-provisioned)             |

---

## 📁 Dataset

The dataset consists of **35 Technical Data Sheets (TDS)** from **BVZyme** bakery enzyme products. The original PDFs were converted to Markdown for structured extraction and are stored in the [`dataset/`](dataset/) folder.

🔗 **Original PDFs:** [Google Drive — BVZyme TDS Collection](https://drive.google.com/drive/folders/10nR80LKvyVeTyE8qD8bBi1MPdgvmvLMJ)

### Covered Enzyme Families

| Enzyme Type                | Products                                                            | Typical Dosage |
| -------------------------- | ------------------------------------------------------------------- | -------------- |
| **Ascorbic Acid** (E300)   | Acide Ascorbique                                                    | 20–300 ppm     |
| **Alpha-Amylase** (Fungal) | AF110, AF220, AF330, AF SX                                          | 2–25 ppm       |
| **Maltogenic Amylase**     | A FRESH101, A FRESH202, A FRESH303, A SOFT205, A SOFT305, A SOFT405 | 10–100 ppm     |
| **Glucose Oxidase**        | GOX 110, GO MAX 63, GO MAX 65                                       | 5–50 ppm       |
| **Lipase**                 | L MAX X, L MAX63, L MAX64, L MAX65, L55, L65                        | 2–60 ppm       |
| **Transglutaminase**       | TG881, TG883, TG MAX63, TG MAX64                                    | 5–40 ppm       |
| **Xylanase** (Bacterial)   | HCB708, HCB709, HCB710                                              | 5–30 ppm       |
| **Xylanase** (Fungal)      | HCF400, HCF500, HCF600, HCF MAX X, HCF MAX63, HCF MAX64             | 0.5–70 ppm     |
| **Amyloglucosidase**       | AMG880, AMG1400                                                     | 10–100 ppm     |

---

## 🚀 Getting Started

### Prerequisites

- **Docker** and **Docker Compose** installed on your machine.
- No other dependencies are required — everything runs inside containers.

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/MarouaHattab/AMT--ROSE-BLANCHE.git
cd AMT--ROSE-BLANCHE

# 2. Start the entire stack (8 services)
cd rose-blanche-api
docker compose up --build -d
```

That's it. The API starts at **http://localhost:8000** and the dataset is **automatically ingested on first startup**.

### Services & Ports

Once running, you have access to the following services:

| Service                 | URL                        | Credentials         | Description                        |
| ----------------------- | -------------------------- | ------------------- | ---------------------------------- |
| **FastAPI (Swagger)**   | http://localhost:8000/docs | —                   | Interactive API documentation      |
| **Web UI**              | http://localhost:8000      | —                   | Search interface (HTML + Tailwind) |
| **RabbitMQ Management** | http://localhost:15672     | guest / guest       | Message broker dashboard           |
| **Flower**              | http://localhost:5555      | —                   | Celery task monitoring             |
| **Prometheus**          | http://localhost:9090      | —                   | Metrics & PromQL queries           |
| **Grafana**             | http://localhost:3000      | admin / roseblanche | Production dashboards              |

### Docker Services

| Container                    | Image                      | Port(s)      | Role                                   |
| ---------------------------- | -------------------------- | ------------ | -------------------------------------- |
| `rose-blanche-db`            | `pgvector/pgvector:pg17`   | 5432         | PostgreSQL + pgvector                  |
| `rose-blanche-api`           | Custom (Python 3.11)       | 8000         | FastAPI backend + embedding model      |
| `rose-blanche-rabbitmq`      | `rabbitmq:3.13-management` | 5672 / 15672 | AMQP message broker + management UI    |
| `rose-blanche-celery-worker` | Custom (Python 3.11)       | —            | Background task worker (concurrency=2) |
| `rose-blanche-celery-beat`   | Custom (Python 3.11)       | —            | Periodic task scheduler                |
| `rose-blanche-flower`        | Custom (Python 3.11)       | 5555         | Celery monitoring dashboard            |
| `rose-blanche-prometheus`    | `prom/prometheus:v2.53.0`  | 9090         | Metrics collection & storage (30d)     |
| `rose-blanche-grafana`       | `grafana/grafana:11.1.0`   | 3000         | Production dashboards & alerts         |

### Environment Variables

All configuration is handled via environment variables. The defaults work out of the box with Docker Compose:

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
| `DEFAULT_TOP_K`             | `3`                                  | Default number of search results    |
| `AUTO_INGEST`               | `true`                               | Auto-ingest dataset on startup      |
| `CELERY_BROKER_URL`         | `amqp://guest:guest@rabbitmq:5672//` | RabbitMQ connection URL             |
| `CELERY_RESULT_BACKEND`     | `rpc://`                             | Celery result backend               |

### Local Development (Without Docker)

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 2. Install dependencies
cd rose-blanche-api
pip install -r requirements.txt

# 3. Start PostgreSQL with pgvector (must be installed separately)

# 4. Set environment variables (see table above)

# 5. Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔌 API Reference

### Health Check

```http
GET /api/v1/
```

Returns API metadata: app name, version, embedding model info, and default top_k.

### Data Ingestion

| Method | Endpoint                        | Description                                     |
| ------ | ------------------------------- | ----------------------------------------------- |
| `POST` | `/api/v1/data/ingest`           | Ingest all `.md` files from the dataset (sync)  |
| `POST` | `/api/v1/data/reingest`         | Drop all data and re-ingest from scratch (sync) |
| `GET`  | `/api/v1/data/documents`        | List all ingested documents with metadata       |
| `GET`  | `/api/v1/data/embeddings/count` | Get total number of stored embeddings           |

**Ingest Request:**

```json
{
  "chunk_size": 500,
  "overlap_size": 50
}
```

### Semantic Search

```http
POST /api/v1/search/
```

**Request:**

```json
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

**Search Stats:**

```http
GET /api/v1/search/stats
```

### Async Tasks (Celery)

| Method   | Endpoint                  | Description                                     |
| -------- | ------------------------- | ----------------------------------------------- |
| `POST`   | `/api/v1/tasks/ingest`    | Submit async ingestion (returns 202 + task_id)  |
| `POST`   | `/api/v1/tasks/reingest`  | Submit async re-ingestion                       |
| `GET`    | `/api/v1/tasks/{task_id}` | Poll task status (PENDING → PROGRESS → SUCCESS) |
| `DELETE` | `/api/v1/tasks/{task_id}` | Revoke (cancel) a running task                  |
| `GET`    | `/api/v1/tasks/`          | List all active tasks                           |

**Poll Response Example:**

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

---

## 📊 Monitoring & Observability

Rose Blanche includes a full production-grade observability stack. All dashboards and datasources are **auto-provisioned on startup** — no manual configuration required.

### Grafana — RAG Evaluation Dashboard

The Grafana dashboard at **http://localhost:3000** (login: `admin` / `roseblanche`) contains **23 panels** organized into 5 sections:

| Section                   | Panels | What It Tracks                                                                                                      |
| ------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------- |
| **🌹 Overview**           | 6      | Total requests, success rate, avg cosine score, avg ingredient coverage, P95 latency, total embeddings              |
| **🔍 Search Quality**     | 4      | Cosine score distribution (P50/P75/P90/P99), ingredient coverage, detection vs coverage rates, avg score per search |
| **⚡ Performance**        | 4      | Latency percentiles, request rate (req/s), HTTP duration by endpoint, response status codes                         |
| **📥 Ingestion Pipeline** | 5      | Documents ingested, fragments count, ingestion runs (success/error), ingestion duration, Celery tasks               |
| **🏥 System Health**      | 4      | API up/down status, process memory (RSS + virtual), open file descriptors                                           |

<p align="center">
  <img src="demo/Grafana/grafana.png" alt="Grafana — RAG Evaluation Dashboard" width="800"/>
</p>
<p align="center"><em>Grafana Dashboard — KPI overview cards, search quality metrics, and latency percentiles</em></p>

### Prometheus — Metrics Collection

Prometheus at **http://localhost:9090** scrapes the FastAPI `/metrics` endpoint every 15 seconds. Key custom metrics exposed:

```
# Search quality
rose_blanche_search_requests_total{status="success|no_results|error"}
rose_blanche_cosine_score_bucket{le="0.1|...|1.0"}
rose_blanche_ingredient_coverage_bucket{le="0.0|...|1.0"}
rose_blanche_ingredients_detected_total{ingredient="..."}
rose_blanche_ingredients_covered_total{ingredient="..."}

# Performance
rose_blanche_search_latency_seconds_bucket{le="0.05|...|10.0"}

# Ingestion
rose_blanche_ingestion_runs_total{type="ingest|reingest", status="success|error"}
rose_blanche_ingestion_documents_total
rose_blanche_ingestion_fragments_total

# Celery
rose_blanche_celery_tasks_submitted_total{task_name="..."}
rose_blanche_celery_tasks_completed_total{task_name="...", status="SUCCESS|FAILURE"}
```

<p align="center">
  <img src="demo/prometheus/prometheus .png" alt="Prometheus — Targets" width="800"/>
</p>
<p align="center"><em>Prometheus Targets — API endpoint scrape healthy (UP) with 15-second intervals</em></p>

### Flower — Celery Monitoring

Flower at **http://localhost:5555** provides real-time visibility into:

- Worker status (online/offline, active tasks, processed count)
- Task history (success, failure, retry, runtime)
- Queue details (pending messages, consumers)

<p align="center">
  <img src="demo/flower/flower.png" alt="Flower — Worker Overview" width="800"/>
</p>
<p align="center"><em>Flower — Celery worker overview with task success/failure counts</em></p>

<p align="center">
  <img src="demo/flower/flower-in-details.png" alt="Flower — Task Details" width="800"/>
</p>
<p align="center"><em>Flower — Detailed task view with arguments, runtime, and state transitions</em></p>

### RabbitMQ — Message Broker

RabbitMQ Management at **http://localhost:15672** (login: `guest` / `guest`) shows:

- Broker connections and channels
- Queue depth and message rates
- Consumer activity

<p align="center">
  <img src="demo/rabbit-mq/overview.png" alt="RabbitMQ — Overview" width="800"/>
</p>
<p align="center"><em>RabbitMQ Management — Broker overview with node health and message rates</em></p>

<p align="center">
  <img src="demo/rabbit-mq/queues.png" alt="RabbitMQ — Queues" width="800"/>
</p>
<p align="center"><em>RabbitMQ Queues — Celery task queue with message throughput</em></p>

---

## 🧪 Postman Tests

A complete Postman collection is provided for testing all API endpoints.

### How to Use

1. Open **Postman**.
2. Click **Import** → select [`rose-blanche-api/postman/Rose-Blanche-RAG-API.postman_collection.json`](rose-blanche-api/postman/Rose-Blanche-RAG-API.postman_collection.json).
3. The collection variable `{{base_url}}` defaults to `http://localhost:8000`.
4. Run the collection or execute individual requests.

### Test Coverage

| Folder                   | Tests | What It Verifies                                                         |
| ------------------------ | ----- | ------------------------------------------------------------------------ |
| **Health & Info**        | 1     | API welcome endpoint, model metadata                                     |
| **Data Ingestion**       | 5     | Ingest, re-ingest, list documents, embeddings count                      |
| **Semantic Search**      | 8     | Challenge questions (FR/EN), single-ingredient, multi-ingredient queries |
| **Search Statistics**    | 1     | Model info, dimension, similarity method                                 |
| **Async Tasks (Celery)** | 5     | Submit ingest/reingest, poll status, revoke task, list active tasks      |

Every request includes **automated assertions** that verify:

- ✅ HTTP status codes (200, 202)
- ✅ Response signal values (`search_success`, `ingestion_success`)
- ✅ Result count matches `top_k`
- ✅ Relevance scores above threshold
- ✅ Ingredient detection and coverage
- ✅ Correct model and dimension metadata

<p align="center">
  <img src="demo/postman/postman-test.png" alt="Postman — Test Results" width="800"/>
</p>
<p align="center"><em>Postman Test Results — All 20 assertions passing across 5 test folders</em></p>

---

## 📂 Project Structure

```
.
├── dataset/                              # 35 Markdown TDS files (converted from PDF)
│   ├── acide ascorbique.md
│   ├── BVZyme TDS AF110.md
│   └── ... (35 files total)
│
├── demo/                                 # Screenshots and demo assets
│   ├── banner.png                        # Project banner
│   ├── logo.png                          # Project logo
│   ├── demo.gif                          # Application demo recording
│   ├── fastapi.png                       # FastAPI Swagger UI
│   ├── docker/docker.png                 # Docker containers
│   ├── flower/flower.png                 # Flower overview
│   ├── flower/flower-in-details.png      # Flower task details
│   ├── Grafana/grafana.png               # Grafana dashboard
│   ├── prometheus/prometheus .png        # Prometheus targets
│   ├── rabbit-mq/overview.png            # RabbitMQ overview
│   ├── rabbit-mq/queues.png              # RabbitMQ queues
│   └── postman/postman-test.png          # Postman test results
│
├── rose-blanche-api/                     # FastAPI application
│   ├── main.py                           # App entry point + startup/shutdown hooks
│   ├── Dockerfile                        # Python 3.11-slim, pre-downloads model
│   ├── docker-compose.yml                # 8-service orchestration
│   ├── requirements.txt                  # 18 Python packages
│   │
│   ├── controllers/
│   │   ├── BaseController.py             # Base controller class
│   │   ├── DataController.py             # Ingestion: read → chunk → embed → store
│   │   └── SearchController.py           # Search: expand → embed → cosine → RRF
│   │
│   ├── helpers/
│   │   ├── config.py                     # Pydantic settings (env-based)
│   │   └── metrics.py                    # Prometheus custom metrics definitions
│   │
│   ├── models/
│   │   ├── BaseDataModel.py              # Base async model
│   │   ├── DocumentModel.py              # Documents table CRUD
│   │   ├── EmbeddingModel.py             # Embeddings table CRUD
│   │   ├── db_schemes/
│   │   │   ├── base.py                   # SQLAlchemy declarative base
│   │   │   └── schemes.py               # Document, Embedding, RetrievedFragment
│   │   └── enums/
│   │       └── ResponseEnums.py          # API response signal enums
│   │
│   ├── celery_app.py                     # Celery config + Beat schedule
│   │
│   ├── tasks/
│   │   └── ingestion_tasks.py            # Background: ingest, reingest, health check
│   │
│   ├── routes/
│   │   ├── base.py                       # GET /api/v1/
│   │   ├── data.py                       # Sync ingestion endpoints
│   │   ├── search.py                     # Semantic search endpoints (instrumented)
│   │   ├── tasks.py                      # Async task endpoints
│   │   └── schemes/search.py            # Pydantic request schemas
│   │
│   ├── stores/
│   │   ├── embedding/EmbeddingService.py # sentence-transformers wrapper
│   │   └── vectordb/
│   │       ├── PGVectorProvider.py       # pgvector cosine search
│   │       └── VectorDBEnums.py          # Distance method enums
│   │
│   ├── static/index.html                # Web UI (Tailwind CSS)
│   │
│   ├── postman/
│   │   └── Rose-Blanche-RAG-API.postman_collection.json
│   │
│   ├── monitoring/
│   │   ├── prometheus/prometheus.yml     # Scrape config (15s interval)
│   │   └── grafana/
│   │       ├── provisioning/
│   │       │   ├── datasources/datasource.yml
│   │       │   └── dashboards/dashboard.yml
│   │       └── dashboards/
│   │           └── rose-blanche-dashboard.json
│   │
│   └── tests/
│       └── test_search_accuracy.py       # Automated accuracy tests
│
└── README.md
```

---

## 🔍 How It Works

### 1. Data Ingestion Pipeline

```
PDF (Google Drive) → Markdown → Structured Extraction → Smart Chunking → Embedding → pgvector
```

The ingestion pipeline converts raw PDF technical data sheets into searchable vector embeddings:

- **PDF → Markdown** — Original PDFs from Google Drive are pre-converted to structured Markdown files stored in `dataset/`.
- **Structured Extraction** — Each Markdown file is parsed to extract product name, enzyme type, enzymatic activity, recommended dosages, applications, and storage conditions.
- **Bilingual Enrichment** — French ↔ English synonyms are added to each chunk (e.g., "amylase fongique" ↔ "fungal amylase") to improve cross-language retrieval.
- **Smart Chunking** — Text is split into semantic chunks with configurable size (default: 500 chars) and overlap (default: 50 chars) to preserve context across boundaries.
- **Embedding** — Each chunk is encoded into a 384-dimensional dense vector using `all-MiniLM-L6-v2`.
- **Storage** — Vectors are stored in PostgreSQL with the pgvector extension, enabling native cosine similarity queries.
- **Async Mode** — Ingestion can also run as a background Celery task via `POST /api/v1/tasks/ingest`, returning a task_id for polling.

### 2. Semantic Search Pipeline

```
Question → Ingredient Detection → Query Expansion (FR↔EN) → Multi-Query → Embedding → Cosine Search → RRF → Results
```

The search pipeline is designed to handle multi-ingredient questions accurately:

- **Ingredient Detection** — The query is scanned for known enzyme names and bakery terms (supports both French and English).
- **Query Expansion** — Bakery-specific terms are translated between French and English to maximize recall.
- **Multi-Query Decomposition** — If multiple ingredients are detected, specialized sub-queries are generated for each ingredient.
- **Embedding** — Each sub-query is encoded into a 384D vector.
- **Cosine Similarity Search** — pgvector performs nearest-neighbor search for each sub-query independently.
- **Reciprocal Rank Fusion (RRF)** — Results from all sub-queries are merged into a single ranked list using RRF, which balances precision across ingredients.
- **Coverage Metrics** — The response includes how many detected ingredients are represented in the final results (e.g., "3/3 ingredients found").

### 3. Asynchronous Processing (Celery + RabbitMQ)

```
FastAPI ──send_task()──▶ RabbitMQ ──deliver──▶ Celery Worker ──▶ PostgreSQL
  ▲                                                   │
  └───── poll GET /tasks/{id} ◀──────── result ───────┘
```

| Component         | Role                                                                               |
| ----------------- | ---------------------------------------------------------------------------------- |
| **Celery Worker** | Executes heavy ingestion and embedding tasks in background processes               |
| **RabbitMQ**      | AMQP message broker — provides reliable task queue with persistence                |
| **Celery Beat**   | Scheduler — triggers periodic re-ingestion (daily) and health checks (every 5 min) |
| **Flower**        | Real-time web dashboard for monitoring workers, tasks, and queues                  |

**Scheduled Tasks:**

| Task                 | Interval        | Description                      |
| -------------------- | --------------- | -------------------------------- |
| `health_check`       | Every 5 minutes | Verifies database connectivity   |
| `scheduled_reingest` | Every 24 hours  | Full re-ingestion of the dataset |

### 4. Observability (Prometheus + Grafana)

```
FastAPI ── /metrics ──▶ Prometheus ──▶ Grafana Dashboards
              (scrape 15s)    (30d retention)    (23 panels, auto-provisioned)
```

The observability stack ensures production readiness:

- **Prometheus Instrumentation** — Every HTTP request and search operation is measured. Custom metrics track cosine similarity scores, ingredient coverage, search latency, ingestion durations, and Celery task counts.
- **Prometheus Server** — Scrapes `/metrics` every 15 seconds and stores time-series data with 30-day retention.
- **Grafana Dashboard** — A 23-panel dashboard, organized into 5 sections (Overview, Search Quality, Performance, Ingestion, System Health), is auto-provisioned on container startup with no manual configuration required.

---

## 📜 License

This project was developed for the **AMT — Rose Blanche** challenge during **AI Night 2K26**.
