import asyncio
import json
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse

from agent import run_agent
from evaluation import evaluate_async, get_latest_eval
from guardrails import check_injection
from rate_limiter import limiter, rate_limit_exceeded_handler
from retriever import ingest_documents

app = FastAPI(title="DTQ RAG Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class IngestRequest(BaseModel):
    documents: list[str]
    metadata: Optional[list[dict]] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/rag/chat")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatRequest):
    if check_injection(body.message):
        raise HTTPException(status_code=400, detail="Potential prompt injection detected.")

    session_id = body.session_id or str(uuid.uuid4())

    async def event_stream():
        full_response = ""
        retrieved_contexts: list[str] = []

        async for chunk, contexts in run_agent(body.message, session_id):
            if chunk:
                full_response += chunk
                yield {
                    "event": "message",
                    "data": json.dumps({"chunk": chunk, "session_id": session_id}),
                }
            if contexts is not None:
                retrieved_contexts = contexts

        yield {
            "event": "done",
            "data": json.dumps({"session_id": session_id}),
        }

        # Fire-and-forget evaluation — does not block the stream
        asyncio.create_task(
            evaluate_async(body.message, full_response, retrieved_contexts, session_id)
        )

    # Pass session_id via header so the client can read it before the first token
    return EventSourceResponse(
        event_stream(),
        headers={"X-Session-ID": session_id},
    )


@app.post("/api/rag/ingest")
async def ingest(body: IngestRequest):
    count = await ingest_documents(body.documents, body.metadata or [])
    return {"ingested": count}


@app.get("/api/rag/evaluate/{session_id}")
async def get_evaluation(session_id: str):
    result = await get_latest_eval(session_id)
    if not result:
        return JSONResponse(
            status_code=404,
            content={"error": "No evaluation found for this session yet."},
        )
    return result
