# Distributed Task Queue

A production-grade distributed task queue built with **Go**, **Redis**, **React**, and **FastAPI**. Features priority scheduling, automatic retries, dead-letter handling, stale job recovery, a LangGraph ReAct RAG agent with hybrid retrieval, and a live React dashboard — all orchestrated with Docker Compose.

---

## Architecture

```
┌─────────────────────┐
│   React Frontend    │  :80  (nginx — serves UI + proxies API calls)
└────────┬────────────┘
         │
    ┌────┴──────────────────────────┐
    │           nginx proxy          │
    └────┬─────────────┬────────────┘
         │             │
         ▼             ▼
┌──────────────┐  ┌──────────────────┐     ┌──────────────────┐
│  API (Gin)   │  │  RAG Service     │     │  Redis           │
│  :8080       │  │  (FastAPI) :8000 │────▶│  (session memory │
└──────┬───────┘  └──────┬───────────┘     │   + queue state) │
       │                 │                 └──────────────────┘
       ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│  Redis Queue │  │  ChromaDB        │
│  (Sorted Set)│  │  (vector store)  │
└──────┬───────┘  └──────────────────┘
       │
       │ poll
┌──────▼───────┐
│ Worker Pool  │
│ 2 replicas × │
│ 5 goroutines │
└──────────────┘
```

### Components

| Service | Language / Stack | Role |
|---|---|---|
| **API** | Go / Gin | Accepts jobs, exposes status, stats, and dead-letter endpoints |
| **Worker** | Go | Pool of goroutines that dequeue and process jobs (including `ai_agent` via Anthropic Claude) |
| **Redis** | Redis 7 | Priority queue, processing tracker, dead-letter list, RAG session memory, eval cache |
| **RAG Service** | Python / FastAPI | LangGraph ReAct agent, hybrid retrieval, SSE streaming chat, RAGAS evaluation |
| **ChromaDB** | ChromaDB | Persistent vector store for dense retrieval |
| **Frontend** | React + Vite / nginx | Live dashboard — queue stats, job submission, RAG chat, dead-letter inspector |

---

## Features

### Task Queue
- **Priority scheduling** — High / Medium / Low; jobs sorted by priority then FIFO within the same level
- **Automatic retries** — configurable `max_retries` per job; failed jobs are re-enqueued with a back-off penalty
- **Dead-letter queue** — jobs that exhaust retries are parked with their last error; listable via API
- **API retry** — dead-letter jobs can be re-enqueued via a single API call, resetting retries to zero
- **Stale job recovery** — background sweeper re-enqueues jobs stuck in `processing` for > 5 minutes
- **Per-job timeout** — each handler gets a 30-second context deadline; hung jobs are automatically failed
- **Horizontal scaling** — worker replicas controlled by `WORKER_POOL_SIZE`; Compose runs 2 replicas out of the box

### AI / RAG Agent
- **LangGraph ReAct architecture** — agent reasons step-by-step, calling retrieval tools before answering
- **HyDE query rewriting** — generates a hypothetical answer to improve dense retrieval recall
- **Hybrid BM25 + dense retrieval** — `EnsembleRetriever` (weights 0.4 / 0.6) merges keyword and semantic results
- **Cross-encoder reranking** — `cross-encoder/ms-marco-MiniLM-L-6-v2` reranks 20 candidates to top-6
- **Multilingual embeddings** — `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, 50+ languages); zero index change needed when swapping languages
- **20-turn session memory** — conversation history persisted in Redis per session with 1-hour TTL
- **Per-session rate limiting** — 30 requests/minute per session ID via slowapi
- **Prompt injection guardrails** — regex-based detection blocks common injection patterns before the LLM is called
- **RAGAS evaluation** — async answer relevancy, faithfulness, and context recall scored after every response
- **SSE streaming** — responses stream token-by-token to the frontend via Server-Sent Events
- **`ai_agent` job type** — submit long-running AI tasks to the queue; gets retries, priority, and dead-letter for free

---

## Project Structure

```
.
├── cmd/
│   ├── api/main.go              # API server entrypoint
│   └── worker/main.go           # Worker pool entrypoint (registers job handlers + ai_agent)
├── internal/
│   ├── ai/
│   │   └── claude_client.go     # Anthropic Claude HTTP client (used by ai_agent worker)
│   ├── api/
│   │   ├── handler.go           # HTTP handlers (submit, get, list-dead, retry, stats, health)
│   │   └── router.go            # Gin route registration
│   ├── queue/
│   │   ├── job.go               # Job model, status constants, priority levels
│   │   ├── queue.go             # Queue interface
│   │   └── redis_queue.go       # Redis-backed implementation
│   └── worker/
│       ├── worker.go            # Single worker — polls queue, dispatches handlers
│       └── pool.go              # Worker pool + stale-job sweeper goroutine
├── rag/
│   ├── main.py                  # FastAPI app — /api/rag/chat (SSE), /ingest, /evaluate
│   ├── agent.py                 # LangGraph ReAct agent + HyDE query expansion
│   ├── retriever.py             # Hybrid BM25 + ChromaDB + cross-encoder reranking
│   ├── memory.py                # Redis-backed 20-turn session memory
│   ├── evaluation.py            # Async RAGAS evaluation (relevancy, faithfulness, recall)
│   ├── guardrails.py            # Regex prompt-injection detection
│   ├── rate_limiter.py          # Per-session rate limiting (slowapi)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Tab layout — Queue / RAG Chat / Dead Letter
│   │   ├── App.css              # Dark-theme design system
│   │   ├── api/
│   │   │   ├── queue.js         # Go API client
│   │   │   └── rag.js           # RAG service client (SSE streaming)
│   │   └── components/
│   │       ├── QueueStats.jsx   # Live-polling stats cards
│   │       ├── JobSubmit.jsx    # Job submission form
│   │       ├── JobList.jsx      # Job lookup by ID
│   │       ├── RAGChat.jsx      # Streaming chat + ingest + RAGAS score bars
│   │       └── DeadLetterPanel.jsx # Dead-letter inspector + AI analysis
│   ├── nginx.conf               # Reverse proxy — SPA routing + API forwarding
│   ├── Dockerfile               # Multi-stage: node build → nginx serve
│   ├── package.json
│   └── vite.config.js
├── Dockerfile.api
├── Dockerfile.worker
├── docker-compose.yml
└── go.mod
```

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose v2)
- An [Anthropic API key](https://console.anthropic.com/) for `ai_agent` jobs and the RAG service

### Run the stack

```bash
git clone <repo-url>
cd distributed-task-queue
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build
```

> **First build note:** the RAG image pre-downloads the embedding model (~450 MB) and cross-encoder (~100 MB) so the container starts fast on subsequent runs.

Services start in dependency order: Redis → ChromaDB → API → Worker replicas + RAG → Frontend.

| Service | URL |
|---|---|
| **Frontend (React)** | http://localhost:80 |
| REST API | http://localhost:8080 |
| RAG Service | http://localhost:8000 |
| ChromaDB | http://localhost:8001 |
| Redis | localhost:6379 |

```bash
docker compose down       # stop
docker compose down -v    # stop + wipe volumes
```

### Local development (without Docker)

```bash
# Terminal 1 — Go API
REDIS_ADDR=localhost:6379 go run ./cmd/api

# Terminal 2 — Go Worker
REDIS_ADDR=localhost:6379 ANTHROPIC_API_KEY=sk-ant-... go run ./cmd/worker

# Terminal 3 — RAG service
cd rag && pip install -r requirements.txt
REDIS_ADDR=localhost:6379 ANTHROPIC_API_KEY=sk-ant-... uvicorn main:app --port 8000

# Terminal 4 — React frontend (Vite proxy routes /api/* to local services)
cd frontend && npm install && npm run dev
```

---

## REST API

### `POST /api/v1/jobs` — Submit a job

```bash
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "email",
    "payload": {"to": "user@example.com", "subject": "Hello"},
    "priority": 1,
    "max_retries": 3
  }'
```

**Built-in job types**

| Type | Description |
|---|---|
| `email` | Simulated email send |
| `image_resize` | Simulated image resize (20% failure rate to exercise retries) |
| `report` | Simulated report generation |
| `ai_agent` | Calls Anthropic Claude with `payload.task`; requires `ANTHROPIC_API_KEY` |

**`ai_agent` example**

```bash
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ai_agent",
    "payload": {"task": "Summarize the key benefits of distributed task queues"},
    "priority": 1
  }'
```

**Request fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | ✓ | Must match a registered handler |
| `payload` | object | | Arbitrary JSON passed to the handler |
| `priority` | int | | `1` High, `2` Medium (default), `3` Low |
| `max_retries` | int | | Default `3` |

**Response** `201 Created` — full `Job` object.

---

### `GET /api/v1/jobs/:id` — Get job status

```bash
curl http://localhost:8080/api/v1/jobs/<id>
```

Returns the full job object. Status: `pending` | `processing` | `completed` | `failed` | `dead`.

---

### `GET /api/v1/jobs/dead` — List dead-letter jobs

```bash
curl http://localhost:8080/api/v1/jobs/dead
```

Returns up to 50 dead-letter jobs (newest first) as a JSON array.

---

### `POST /api/v1/jobs/:id/retry` — Retry a dead-letter job

```bash
curl -X POST http://localhost:8080/api/v1/jobs/<id>/retry
```

Resets `retries` to `0`, clears the error, and re-enqueues the job.

---

### `GET /api/v1/stats` — Queue counters

```json
{
  "pending_count": 4,
  "processing_count": 2,
  "completed_count": 137,
  "failed_count": 12,
  "dead_count": 1
}
```

---

### `GET /health` — Liveness probe

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

---

## RAG Service API

### `POST /api/rag/chat` — Streaming chat (SSE)

```bash
curl -N -X POST http://localhost:8000/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is a dead-letter queue?", "session_id": "abc123"}'
```

Streams `event: message` frames (JSON `{"chunk": "...", "session_id": "..."}`) followed by a single `event: done` frame. A new `session_id` is returned if none was provided.

---

### `POST /api/rag/ingest` — Add documents to the knowledge base

```bash
curl -X POST http://localhost:8000/api/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{"documents": ["A dead-letter queue stores jobs that failed all retry attempts..."]}'
```

Documents are embedded with `paraphrase-multilingual-MiniLM-L12-v2`, stored in ChromaDB, and added to the in-memory BM25 corpus.

---

### `GET /api/rag/evaluate/:session_id` — RAGAS scores

```bash
curl http://localhost:8000/api/rag/evaluate/abc123
```

```json
{
  "answer_relevancy": 0.9341,
  "faithfulness": 0.8812,
  "context_recall": 0.9105,
  "question": "What is a dead-letter queue?"
}
```

Scores are computed asynchronously after each response and cached in Redis for 1 hour.

---

## Job Lifecycle

```
                ┌─────────┐
    submit ────▶│ pending │
                └────┬────┘
                     │ dequeue
                ┌────▼──────────┐
                │  processing   │◀──── sweeper rescues stale jobs
                └────┬──────────┘
           ┌─────────┴──────────┐
        success              failure
           │                    │
      ┌────▼─────┐        retries left?
      │completed │         yes │       no
      └──────────┘     ┌───▼────┐   ┌──────┐
                        │ failed │   │ dead │
                        │(retry) │   └──┬───┘
                        └────────┘      │
                                  POST /retry
                                        │
                                   ▼ pending
```

---

## Configuration

### API

| Variable | Default | Description |
|---|---|---|
| `REDIS_ADDR` | `localhost:6379` | Redis address |
| `PORT` | `8080` | HTTP listen port |

### Worker

| Variable | Default | Description |
|---|---|---|
| `REDIS_ADDR` | `localhost:6379` | Redis address |
| `WORKER_POOL_SIZE` | `5` | Concurrent goroutines per replica |
| `ANTHROPIC_API_KEY` | — | Required for `ai_agent` jobs |

### RAG Service

| Variable | Default | Description |
|---|---|---|
| `REDIS_ADDR` | `localhost:6379` | Redis address (session memory + eval cache) |
| `ANTHROPIC_API_KEY` | — | Required for LLM completions and RAGAS evaluation |
| `CHROMA_HOST` | `localhost` | ChromaDB host |
| `CHROMA_PORT` | `8001` | ChromaDB port |

---

## Scaling Workers

```bash
docker compose up -d --scale worker=4
```

Adjust goroutines per replica via `WORKER_POOL_SIZE` in `docker-compose.yml`.

---

## Adding a New Job Type

1. Register a handler in `cmd/worker/main.go`:

```go
handlers["transcode"] = func(ctx context.Context, job *queue.Job) error {
    // access job.Payload["input_url"] etc.
    return nil
}
```

2. Submit jobs with `"type": "transcode"` via the API or the React frontend.

---

## Redis Data Model

| Key | Type | Contents |
|---|---|---|
| `queue:pending` | Sorted Set | Job IDs scored by `priority × 10¹⁰ + unix_ms` |
| `queue:processing` | Hash | `jobID → enqueue_timestamp_ms` |
| `queue:dead` | List | Dead job IDs (newest first) |
| `job:<id>` | String | JSON-serialised `Job` struct |
| `stats:completed` | String | Running completed counter |
| `stats:failed` | String | Running failed counter |
| `stats:dead` | String | Running dead counter |
| `rag:session:<id>:history` | List | Up to 20 turns of chat history (TTL 1h) |
| `rag:eval:<id>` | String | JSON RAGAS scores for session (TTL 1h) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | [Gin](https://github.com/gin-gonic/gin) v1.10 |
| Redis client (Go) | [go-redis](https://github.com/redis/go-redis) v9 |
| ID generation | [google/uuid](https://github.com/google/uuid) v1.6 |
| LLM (worker + RAG) | [Anthropic Claude](https://www.anthropic.com/) (`claude-sonnet-4-20250514`) |
| RAG framework | [LangGraph](https://github.com/langchain-ai/langgraph) + [LangChain](https://github.com/langchain-ai/langchain) |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Vector store | [ChromaDB](https://www.trychroma.com/) |
| RAG evaluation | [RAGAS](https://docs.ragas.io/) |
| RAG API | [FastAPI](https://fastapi.tiangolo.com/) + sse-starlette |
| Frontend | [React](https://react.dev/) 18 + [Vite](https://vitejs.dev/) 6 |
| Frontend serving | nginx (multi-stage Docker build) |
| Container runtime | Docker + Docker Compose v2 |
| Go version | 1.22 |

---

## Architecture

```
┌─────────────┐    HTTP     ┌──────────────┐    Redis     ┌──────────────────┐
│   Client    │ ──────────▶ │   API (Gin)  │ ──────────▶  │  Redis (Sorted   │
│             │             │  :8080       │              │  Set + Hash)     │
└─────────────┘             └──────────────┘              └────────┬─────────┘
                                                                   │
                            ┌──────────────┐                       │ poll
                            │  Dashboard   │ ◀─────────────────────┤
                            │  (Streamlit) │                       │
                            │  :8501       │              ┌────────▼─────────┐
                            └──────────────┘              │  Worker Pool     │
                                                          │  (2 replicas ×   │
                                                          │   5 goroutines)  │
                                                          └──────────────────┘
```

### Components

| Service | Language | Role |
|---|---|---|
| **API** | Go / Gin | Accepts jobs, exposes status & stats endpoints |
| **Worker** | Go | Pool of goroutines that dequeue and process jobs |
| **Redis** | Redis 7 | Priority queue (sorted set), processing tracker (hash), dead-letter (list) |
| **Dashboard** | Python / Streamlit | Live monitoring UI — submit jobs, view metrics, inspect dead-letter queue |

---

## Features

- **Priority scheduling** — three levels (High / Medium / Low); jobs sorted by priority then FIFO within the same level
- **Automatic retries** — configurable `max_retries` per job; failed jobs are re-enqueued with a back-off penalty score
- **Dead-letter queue** — jobs that exhaust all retries are parked in a dead-letter list with their last error
- **API retry** — dead-letter jobs can be re-enqueued via a single API call, resetting retries to zero
- **Stale job recovery** — a background sweeper re-enqueues jobs stuck in `processing` for > 5 minutes (handles crashed workers)
- **Per-job timeout** — each handler is given a 30-second context deadline; hung jobs are automatically failed
- **Health check** — `GET /health` endpoint wired into Docker Compose `depends_on` so workers/dashboard only start once the API is ready
- **Horizontal scaling** — worker replicas are controlled by a single `WORKER_POOL_SIZE` env var; Compose runs 2 replicas out of the box

---

## Project Structure

```
.
├── cmd/
│   ├── api/main.go           # API server entrypoint
│   └── worker/main.go        # Worker pool entrypoint (registers job handlers)
├── internal/
│   ├── api/
│   │   ├── handler.go        # HTTP handlers (submit, get, retry, stats, health)
│   │   └── router.go         # Gin route registration
│   ├── queue/
│   │   ├── job.go            # Job model, status constants, priority levels
│   │   ├── queue.go          # Queue interface
│   │   └── redis_queue.go    # Redis-backed implementation
│   └── worker/
│       ├── worker.go         # Single worker — polls queue, dispatches handlers
│       └── pool.go           # Worker pool + stale-job sweeper goroutine
├── dashboard/
│   ├── app.py                # Streamlit dashboard
│   ├── Dockerfile
│   └── requirements.txt
├── Dockerfile.api
├── Dockerfile.worker
├── docker-compose.yml
└── go.mod
```

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose v2)

### Run the stack

```bash
git clone <repo-url>
cd distributed-task-queue
docker compose up --build
```

All four services start automatically in the correct order (Redis → API → Workers + Dashboard).

| Service | URL |
|---|---|
| REST API | http://localhost:8080 |
| Dashboard | http://localhost:8501 |
| Redis | localhost:6379 |

To stop and remove containers:

```bash
docker compose down
```

To wipe the Redis volume as well:

```bash
docker compose down -v
```

---

## REST API

### `POST /api/v1/jobs` — Submit a job

```bash
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "email",
    "payload": {"to": "user@example.com", "subject": "Hello"},
    "priority": 1,
    "max_retries": 3
  }'
```

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | ✓ | Job type — must match a registered handler (`email`, `image_resize`, `report`) |
| `payload` | object | | Arbitrary JSON passed to the handler |
| `priority` | int | | `1` = High, `2` = Medium (default), `3` = Low |
| `max_retries` | int | | Max retry attempts before dead-lettering (default `3`) |

**Response** `201 Created`

```json
{
  "id": "de0316c7-d4f8-4cbf-bc26-06869af44ad9",
  "type": "email",
  "payload": {"to": "user@example.com", "subject": "Hello"},
  "priority": 1,
  "status": "pending",
  "retries": 0,
  "max_retries": 3,
  "created_at": "2026-05-19T00:04:18.963577345Z",
  "updated_at": "2026-05-19T00:04:18.963577345Z"
}
```

---

### `GET /api/v1/jobs/:id` — Get job status

```bash
curl http://localhost:8080/api/v1/jobs/de0316c7-d4f8-4cbf-bc26-06869af44ad9
```

Returns the full job object. Status will be one of: `pending`, `processing`, `completed`, `failed`, `dead`.

**Errors**

| Code | Meaning |
|---|---|
| `404` | Job ID does not exist |

---

### `POST /api/v1/jobs/:id/retry` — Retry a dead-letter job

```bash
curl -X POST http://localhost:8080/api/v1/jobs/<id>/retry
```

Removes the job from the dead-letter list, resets `retries` to `0`, clears the error, and re-enqueues it. Returns the updated job object.

**Errors**

| Code | Meaning |
|---|---|
| `400` | Job exists but is not in `dead` status |
| `404` | Job ID does not exist |

---

### `GET /api/v1/stats` — Queue counters

```bash
curl http://localhost:8080/api/v1/stats
```

```json
{
  "pending_count": 4,
  "processing_count": 2,
  "completed_count": 137,
  "failed_count": 12,
  "dead_count": 1
}
```

---

### `GET /health` — Liveness probe

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

Used by Docker Compose healthcheck; returns `200` as soon as the server is ready.

---

## Job Lifecycle

```
                ┌─────────┐
    submit ────▶│ pending │
                └────┬────┘
                     │ dequeue
                ┌────▼──────────┐
                │  processing   │◀──── sweeper rescues stale jobs
                └────┬──────────┘
           ┌─────────┴──────────┐
        success              failure
           │                    │
      ┌────▼─────┐        retries left?
      │completed │         yes │       no
      └──────────┘     ┌───▼────┐   ┌──────┐
                        │ failed │   │ dead │
                        │(retry) │   └──┬───┘
                        └────────┘      │
                                  POST /retry
                                        │
                                   ▼ pending
```

---

## Configuration

All configuration is via environment variables.

### API

| Variable | Default | Description |
|---|---|---|
| `REDIS_ADDR` | `localhost:6379` | Redis address |
| `PORT` | `8080` | HTTP listen port |

### Worker

| Variable | Default | Description |
|---|---|---|
| `REDIS_ADDR` | `localhost:6379` | Redis address |
| `WORKER_POOL_SIZE` | `5` | Number of concurrent worker goroutines per replica |

### Dashboard

| Variable | Default | Description |
|---|---|---|
| `API_URL` | `http://localhost:8080` | Base URL of the API service |
| `REDIS_ADDR` | `localhost:6379` | Redis address (used for in-flight job inspection) |

---

## Scaling Workers

To increase worker replicas at runtime:

```bash
docker compose up -d --scale worker=4
```

To adjust goroutines per replica, set `WORKER_POOL_SIZE` in `docker-compose.yml`.

---

## Adding a New Job Type

1. Register a handler in `cmd/worker/main.go`:

```go
handlers["transcode"] = func(ctx context.Context, job *queue.Job) error {
    // access job.Payload["input_url"] etc.
    return nil
}
```

2. Submit jobs with `"type": "transcode"` via the API.

That's it — no schema changes, no restarts of the API or Redis.

---

## Dashboard

The Streamlit dashboard at **http://localhost:8501** provides:

- **Live metrics** — pending / processing / completed / failed / dead counters
- **Donut chart** — visual job distribution
- **In-flight table** — currently processing jobs and how long they've been running
- **Dead-letter table** — last 10 dead jobs with type, retry count, and error message
- **Job submission form** — submit any job type with custom priority, retries, and JSON payload
- **Auto-refresh** — re-queries the API and Redis every 5 seconds (toggle in sidebar)

---

## Redis Data Model

| Key | Type | Contents |
|---|---|---|
| `queue:pending` | Sorted Set | Job IDs scored by `priority × 10¹⁰ + unix_ms` |
| `queue:processing` | Hash | `jobID → enqueue_timestamp_ms` |
| `queue:dead` | List | Dead job IDs (newest first) |
| `job:<id>` | String | JSON-serialised `Job` struct |
| `stats:completed` | String | Running completed counter |
| `stats:failed` | String | Running failed counter |
| `stats:dead` | String | Running dead counter |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | [Gin](https://github.com/gin-gonic/gin) v1.10 |
| Redis client | [go-redis](https://github.com/redis/go-redis) v9 |
| ID generation | [google/uuid](https://github.com/google/uuid) v1.6 |
| Dashboard | [Streamlit](https://streamlit.io/) + Plotly + Pandas |
| Container runtime | Docker + Docker Compose v2 |
| Go version | 1.22 |
