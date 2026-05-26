"""SmartQueue AI Service — FastAPI application."""
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse

from bot import stream_bot_response
from classifier import classify_ticket
from guardrails import check_injection
from knowledge import seed_knowledge_base
from memory import add_to_history, clear_history, get_history
from recommender import get_recommendations
from simulator import simulate_tickets
from sla import check_sla_status, get_at_risk_jobs


# ── Rate limiter ──────────────────────────────────────────────
def _session_key(request: Request) -> str:
    return request.headers.get("X-Session-ID") or request.client.host


limiter = Limiter(key_func=_session_key)


# ── Lifespan ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        seed_knowledge_base()
    except Exception as exc:
        print(f"[startup] knowledge base seed failed (ChromaDB may not be ready): {exc}")
    yield


app = FastAPI(title="SmartQueue AI Service", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────
class ClassifyRequest(BaseModel):
    text: str
    customer_tier: str = "standard"


class RecommendRequest(BaseModel):
    queue_stats: dict


class BotChatRequest(BaseModel):
    message: str
    ticket: dict = {}
    session_id: str = "default"


class SimulateRequest(BaseModel):
    count: int = 10
    api_base: str = "http://api:8080"


# ── Endpoints ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "smartqueue-ai"}


@app.post("/api/ai/classify")
async def classify(req: ClassifyRequest):
    if check_injection(req.text):
        raise HTTPException(status_code=400, detail="Invalid input detected")
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")
    try:
        result = await classify_ticket(req.text, req.customer_tier)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ai/recommend")
async def recommend(req: RecommendRequest):
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")
    try:
        return await get_recommendations(req.queue_stats)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ai/bot/chat")
@limiter.limit("30/minute")
async def bot_chat(req: BotChatRequest, request: Request):
    if check_injection(req.message):
        raise HTTPException(status_code=400, detail="Invalid input detected")
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    session_id = req.session_id or str(uuid.uuid4())
    history = await get_history(session_id)

    async def stream():
        full = ""
        try:
            async for chunk in stream_bot_response(req.message, req.ticket, history):
                full += chunk
                yield {"data": json.dumps({"chunk": chunk})}
        except Exception as exc:
            yield {"data": json.dumps({"error": str(exc)})}
        finally:
            if full:
                await add_to_history(session_id, req.message, full)
            yield {"data": "[DONE]"}

    response = EventSourceResponse(stream())
    response.headers["X-Session-ID"] = session_id
    return response


@app.post("/api/ai/bot/clear")
async def bot_clear(req: BotChatRequest):
    await clear_history(req.session_id)
    return {"cleared": True}


@app.post("/api/ai/simulate")
async def simulate(req: SimulateRequest):
    if not (1 <= req.count <= 50):
        raise HTTPException(status_code=400, detail="count must be 1–50")
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")
    submitted = await simulate_tickets(req.count, req.api_base)
    return {"submitted": len(submitted), "tickets": submitted}


@app.post("/api/ai/sla-check")
async def sla_check(request: Request):
    body = await request.json()
    jobs = body.get("jobs", [])
    at_risk = get_at_risk_jobs(jobs)
    return {"at_risk": at_risk, "total_checked": len(jobs)}
