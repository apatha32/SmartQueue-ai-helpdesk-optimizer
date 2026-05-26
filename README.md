# SmartQueue — AI Helpdesk Workload Optimizer

A production-grade distributed task queue built on Go, Redis, Python, and React, with an integrated AI layer that classifies support tickets, forecasts workload, and provides a real-time streaming assistant for resolving them. Designed to demonstrate how AI can be embedded into a real distributed system to solve a concrete business problem: managing support ticket floods on busy days.

---

## What It Does

Support teams face unpredictable ticket volume. SmartQueue addresses this with three capabilities:

- **Ticket classification** — incoming support requests are automatically categorised, prioritised (P1-P4), assigned an SLA deadline, and routed to the correct team tier using a large language model.
- **Queue health and recommendations** — the system continuously monitors queue state and generates actionable AI recommendations (escalate, batch, defer, reassign) when workload patterns indicate risk.
- **AI worker bot** — agents can open a chat with an AI assistant that has access to the ticket context and a knowledge base of IT runbooks, powered by streaming inference.

---

## Technical Stack

| Layer | Technology | Purpose |
|---|---|---|
| API server | Go 1.22, Gin | Job ingestion, queue management, REST endpoints |
| Worker pool | Go, goroutines | Concurrent job execution with retry and dead-letter logic |
| Queue backend | Redis 7 (sorted set) | Priority queue, processing tracker, dead-letter list |
| AI service | Python 3.12, FastAPI | Ticket classification, workload recommendations, streaming bot |
| LLM provider | OpenRouter (free tier) | LLaMA 3.3 70B for classification/recommendations, DeepSeek R1 for bot |
| Knowledge base | ChromaDB 0.5, ONNX embeddings | IT runbook retrieval for bot context injection |
| Session memory | Redis | Per-session conversation history for the AI bot |
| Frontend | React 18, Vite, nginx | Live dashboard — Ticket Inbox, Queue Health, AI Bot |
| Infrastructure | Docker Compose | Local multi-service orchestration |
| Kubernetes | Helm, Terraform (EKS), ArgoCD | Production deployment manifests (infra/ directory) |

---

## Architecture

```
Browser
  |
  | HTTP / SSE
  v
React Frontend (nginx :3001)
  |--- /api/v1/*  ---> Go API Server (:8080)
  |--- /api/ai/*  ---> Python AI Service (:8000)
                              |
              +---------------+---------------+
              |               |               |
         Classifier      Recommender        Bot (SSE)
         (LLaMA 3.3)     (LLaMA 3.3)    (DeepSeek R1)
              |               |               |
              +--------> OpenRouter API <------+
                              |
                         ChromaDB
                     (IT runbook vectors)

Go API Server <----> Redis <----> Go Worker Pool (2 replicas x 5 goroutines)
                                      |
                              support_ticket handler
                              email / image_resize / report handlers
```

---

## Key Features

### Distributed Task Queue
- Priority scheduling — jobs sorted by priority (P1-P4) then FIFO within the same level
- Automatic retries — configurable max retries per job; exhausted jobs move to dead-letter
- Dead-letter queue — failed jobs preserved with error context; retryable via API
- Stale job recovery — background sweeper rescues jobs stuck in processing for more than 5 minutes
- Horizontal scaling — worker replicas and pool size independently configurable
- Per-job timeout — each handler receives a context deadline; hung jobs are automatically failed

### AI Capabilities
- Zero-shot ticket classification — category, priority, tier, SLA hours, effort estimate, tags
- Workload recommendation engine — analyses queue state and generates 4 prioritised actions
- Streaming bot — DeepSeek R1 responses stream token-by-token via Server-Sent Events
- Knowledge base RAG — ChromaDB with ONNX MiniLM embeddings; 10 pre-loaded IT runbooks
- Session memory — Redis-backed conversation history per bot session
- Rate limiting — 30 requests/minute per client
- Prompt injection detection — regex-based guardrails applied before every LLM call
- SLA tracking — breach risk scoring (ok / warning / at_risk / breached) computed in real time
- Demo simulator — generates up to 50 realistic classified tickets to demonstrate queue flood behaviour

---

## Project Structure

```
.
├── cmd/
│   ├── api/main.go               # API server entry point
│   └── worker/main.go            # Worker pool entry point; registers all job handlers
├── internal/
│   ├── api/
│   │   ├── handler.go            # HTTP handlers (submit, get, list, dead-letter, retry, stats)
│   │   └── router.go             # Gin route registration
│   ├── queue/
│   │   ├── job.go                # Job model, status constants, priority levels
│   │   ├── queue.go              # Queue interface
│   │   └── redis_queue.go        # Redis implementation (sorted set + hash + list)
│   └── worker/
│       ├── worker.go             # Single worker goroutine
│       └── pool.go               # Pool manager and stale-job sweeper
├── rag/
│   ├── main.py                   # FastAPI app; all /api/ai/* endpoints
│   ├── classifier.py             # Ticket classification via OpenRouter
│   ├── recommender.py            # Workload analysis and recommendations
│   ├── bot.py                    # Streaming AI assistant with RAG context injection
│   ├── knowledge.py              # ChromaDB knowledge base; 10 IT runbooks
│   ├── sla.py                    # SLA breach risk calculator
│   ├── simulator.py              # Demo ticket flood generator
│   ├── memory.py                 # Redis-backed bot session memory
│   ├── guardrails.py             # Prompt injection detection
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Tab layout — Ticket Inbox / Queue Health / AI Bot
│   │   ├── App.css               # Dark-theme design system
│   │   ├── api/index.js          # Unified API client (queue + AI endpoints + SSE)
│   │   └── components/
│   │       ├── TicketInbox.jsx   # Ticket submission with AI classification
│   │       ├── QueueHealth.jsx   # Stats, SLA risk table, AI recommendations
│   │       └── AIBot.jsx         # Streaming chat with ticket context
│   ├── nginx.conf                # Reverse proxy for SPA routing and API forwarding
│   ├── Dockerfile                # Multi-stage: Vite build then nginx serve
│   └── vite.config.js
├── infra/
│   ├── helm/dtq/                 # Helm chart for all services
│   ├── terraform/                # EKS cluster, VPC, ECR, IAM
│   └── argocd/                   # GitOps application manifests
├── Dockerfile.api
├── Dockerfile.worker
├── Dockerfile.huggingface        # Single-container build for HuggingFace Spaces
├── docker-compose.yml
├── supervisord.hf.conf           # Supervisord config for HuggingFace deployment
└── go.mod
```

---

## Running Locally

### Prerequisites

- Docker Desktop (includes Docker Compose v2)
- A free OpenRouter API key — sign up at https://openrouter.ai, go to Keys, and create one

### Steps

```bash
git clone https://github.com/apatha32/DTQ.git
cd DTQ
```

Add your API key to the `.env` file:

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Build and start all services:

```bash
docker compose up --build -d
```

Services start in dependency order: Redis and ChromaDB first, then API and workers, then the AI service, then the frontend.

| Service | URL |
|---|---|
| Frontend (React) | http://localhost:3001 |
| Go API | http://localhost:8080 |
| AI Service (FastAPI) | http://localhost:8000 |
| ChromaDB | http://localhost:8001 |
| Redis | localhost:6379 |

---

## Testing the Application

### 1. Submit and classify a ticket

Open http://localhost:3001 and go to the **Ticket Inbox** tab.

Enter a description such as:
```
Production database is down. All users are getting 500 errors on login.
```

Click **AI Classify**. The system calls LLaMA 3.3 70B via OpenRouter and returns a classification within a few seconds. Expected output:

```
Priority: P1    Category: outage    Tier: engineering
SLA: 1 hour     Estimated effort: 30 min
Tags: database, production, 500-error
```

Click **Submit to Queue** to enqueue the ticket as a `support_ticket` job.

---

### 2. Simulate a ticket flood

On the same tab, set the count to `20` and click **Simulate 20 Tickets**. This submits 20 pre-defined IT support tickets across all categories and priorities. Each ticket is classified before submission.

---

### 3. Check queue health and get AI recommendations

Go to the **Queue Health** tab.

The stats row updates every 5 seconds. The SLA risk table shows any tickets at risk of breaching their deadline.

Click **Analyse Queue** to send the current queue state to the recommendation engine. The AI returns:
- A health score (0-100)
- A summary of the current situation
- Up to 4 prioritised actions (escalate / batch / defer / reassign / alert)

---

### 4. Use the AI bot to resolve a ticket

Go to the **AI Bot** tab.

Select a ticket from the dropdown. The bot receives the ticket details plus relevant excerpts from the IT runbook knowledge base.

Ask a question such as:
```
What are the immediate steps I should take to diagnose this database outage?
```

The response streams in real time using Server-Sent Events. The bot maintains conversation history for the session.

---

### 5. Verify via the REST API directly

Check queue stats:
```bash
curl http://localhost:8080/api/v1/stats
```

List pending jobs:
```bash
curl http://localhost:8080/api/v1/jobs
```

Submit a job manually:
```bash
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "support_ticket",
    "priority": 1,
    "max_retries": 3,
    "payload": {
      "text": "VPN is not connecting for remote employees",
      "category": "access",
      "tier": "tier1",
      "sla_hours": 4,
      "estimated_minutes": 20,
      "summary": "VPN connectivity issue affecting remote workers"
    }
  }'
```

Check a job by ID:
```bash
curl http://localhost:8080/api/v1/jobs/<id>
```

List dead-letter jobs:
```bash
curl http://localhost:8080/api/v1/jobs/dead
```

Retry a dead-letter job:
```bash
curl -X POST http://localhost:8080/api/v1/jobs/<id>/retry
```

Classify a ticket via AI:
```bash
curl -X POST http://localhost:8000/api/ai/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Cannot access email, getting authentication error", "customer_tier": "enterprise"}'
```

Get queue recommendations:
```bash
curl -X POST http://localhost:8000/api/ai/recommend \
  -H "Content-Type: application/json" \
  -d '{"queue_stats": {"pending_count": 15, "processing_count": 3, "dead_count": 2}}'
```

---

## REST API Reference

### Queue Endpoints (Go API — port 8080)

| Method | Path | Description |
|---|---|---|
| POST | /api/v1/jobs | Submit a new job |
| GET | /api/v1/jobs | List pending jobs (up to 100) |
| GET | /api/v1/jobs/:id | Get a job by ID |
| GET | /api/v1/jobs/dead | List dead-letter jobs (up to 50) |
| POST | /api/v1/jobs/:id/retry | Re-enqueue a dead-letter job |
| GET | /api/v1/stats | Queue counters |
| GET | /health | Liveness probe |

### AI Endpoints (FastAPI — port 8000)

| Method | Path | Description |
|---|---|---|
| POST | /api/ai/classify | Classify a ticket (category, priority, SLA, tier, tags) |
| POST | /api/ai/recommend | Analyse queue state and return recommendations |
| POST | /api/ai/bot/chat | Streaming chat (SSE) |
| POST | /api/ai/bot/clear | Clear session history |
| POST | /api/ai/simulate | Submit N demo tickets |
| POST | /api/ai/sla-check | Compute SLA breach risk for a list of jobs |
| GET | /health | Liveness probe |

---

## Job Lifecycle

```
submit
  |
  v
pending  -->  processing  -->  completed
                  |
                  | failure
                  v
              failed (retries left)  -->  re-enqueued
                  |
                  | retries exhausted
                  v
                dead  -->  POST /retry  -->  pending
```

A background sweeper runs every 30 seconds and re-enqueues any jobs that have been in `processing` for more than 5 minutes, handling crashed workers.

---

## Configuration Reference

### API Server

| Variable | Default | Description |
|---|---|---|
| REDIS_ADDR | localhost:6379 | Redis connection address |
| PORT | 8080 | HTTP listen port |

### Worker

| Variable | Default | Description |
|---|---|---|
| REDIS_ADDR | localhost:6379 | Redis connection address |
| WORKER_POOL_SIZE | 5 | Concurrent goroutines per replica |

### AI Service

| Variable | Default | Description |
|---|---|---|
| REDIS_ADDR | localhost:6379 | Redis connection address |
| OPENROUTER_API_KEY | — | Required for all AI features |
| CHROMA_HOST | localhost | ChromaDB hostname |
| CHROMA_PORT | 8000 | ChromaDB port (internal) |

---

## Scaling

```bash
# Run 4 worker replicas
docker compose up -d --scale worker=4

# Increase goroutines per replica
# Set WORKER_POOL_SIZE=10 in docker-compose.yml
```

The Kubernetes manifests in `infra/helm/` include a HorizontalPodAutoscaler for the worker deployment, configured to scale based on Redis queue depth via the Prometheus Adapter.

---

## Adding a New Job Type

Register a handler in `cmd/worker/main.go`:

```go
handlers["send_sms"] = func(ctx context.Context, job *queue.Job) error {
    phone, _ := job.Payload["phone"].(string)
    message, _ := job.Payload["message"].(string)
    return sendSMS(ctx, phone, message)
}
```

Submit jobs of that type via the API:

```bash
curl -X POST http://localhost:8080/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "send_sms", "payload": {"phone": "+1234567890", "message": "Your ticket has been resolved"}, "priority": 2}'
```

---

## Stopping the Stack

```bash
docker compose down        # stop containers, keep volumes
docker compose down -v     # stop containers and delete all data
```
