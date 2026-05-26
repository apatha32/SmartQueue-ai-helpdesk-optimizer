"""Ticket classifier — uses OpenRouter LLM to tag incoming support tickets."""
import json
import os
from functools import lru_cache

from openai import AsyncOpenAI

_CLASSIFY_MODEL = os.getenv("CLASSIFY_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

_PROMPT = """\
You are an IT helpdesk triage system. Classify the ticket below and respond with \
a single JSON object — no markdown, no extra text.

Ticket: {text}
Customer tier: {tier}

Categories  : outage | security | billing | technical | access | feature
Priority    : 1=Critical (outage/security), 2=High (billing/major tech), \
3=Medium (standard tech/access), 4=Low (feature/questions)
Route to    : tier1 | tier2 | billing_team | security_team | engineering
SLA hours   : P1→1h  P2→4h  P3→8h  P4→48h

JSON schema (exactly this, no extra keys):
{{
  "category": "...",
  "priority": <1-4>,
  "tier": "...",
  "sla_hours": <number>,
  "estimated_minutes": <number>,
  "summary": "<≤10 words>",
  "tags": ["tag1", "tag2"]
}}"""


@lru_cache(maxsize=1)
def _llm() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        default_headers={
            "HTTP-Referer": "https://huggingface.co/spaces/ambarish0221/DTQ",
            "X-Title": "SmartQueue",
        },
    )


async def classify_ticket(text: str, customer_tier: str = "standard") -> dict:
    prompt = _PROMPT.format(text=text[:1000], tier=customer_tier)
    resp = await _llm().chat.completions.create(
        model=_CLASSIFY_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=250,
    )
    raw = resp.choices[0].message.content.strip()
    # Strip markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
