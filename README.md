# Distributed Task Queue

A production-ready distributed task queue built with **Go**, **Redis**, and **Streamlit**. Features priority scheduling, automatic retries, dead-letter handling, stale job recovery, and a live monitoring dashboard — all orchestrated with Docker Compose.

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
