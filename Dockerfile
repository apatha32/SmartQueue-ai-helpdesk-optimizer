# =============================================================
# Hugging Face Spaces — single-container build
# All services (Redis, Go API, Go worker, ChromaDB, RAG,
# nginx) run inside one container managed by supervisord.
#
# Build context: project root
# To deploy: copy this file to root as "Dockerfile" when
#            pushing to your HF Space repo.
# =============================================================

# ─────────────────────────────────────────────────────────────
# Stage 1 — Compile Go binaries
# ─────────────────────────────────────────────────────────────
FROM golang:1.22-alpine AS go-builder

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY cmd/     cmd/
COPY internal/ internal/
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/api    ./cmd/api  && \
    CGO_ENABLED=0 GOOS=linux go build -o /out/worker ./cmd/worker

# ─────────────────────────────────────────────────────────────
# Stage 2 — Build React frontend
# ─────────────────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─────────────────────────────────────────────────────────────
# Stage 3 — Final runtime image
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    nginx \
    supervisor \
    wget \
 && rm -rf /var/lib/apt/lists/*

# ── Go binaries ──────────────────────────────────────────────
COPY --from=go-builder /out/api    /usr/local/bin/api
COPY --from=go-builder /out/worker /usr/local/bin/worker

# ── React static assets ──────────────────────────────────────
COPY --from=frontend-builder /app/dist /var/www/html

# ── Python RAG service ───────────────────────────────────────
WORKDIR /app/rag
COPY rag/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rag/ .

# ── Configs ──────────────────────────────────────────────────
COPY supervisord.hf.conf /etc/supervisor/conf.d/supervisord.conf
COPY nginx.hf.conf       /etc/nginx/sites-available/default

# Activate our nginx site and allow root worker processes
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default && \
    sed -i 's/^user www-data;/user root;/' /etc/nginx/nginx.conf && \
    mkdir -p /var/log/supervisor /data/chroma /run/nginx

EXPOSE 7860

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
