"""Ticket classifier — uses OpenRouter LLM to tag incoming support tickets."""
import json
import os
from functools import lru_cache

from openai import AsyncOpenAI

_CLASSIFY_MODEL = os.getenv("CLASSIFY_MODEL", "llama-3.3-70b-versatile")

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
    # Prefer Groq (free tier, fast); fall back to OpenRouter if key provided
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        return AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            max_retries=0,
        )
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        max_retries=0,  # fail fast — callers have their own fallback
        default_headers={
            "HTTP-Referer": "https://huggingface.co/spaces/ambarish0221/DTQ",
            "X-Title": "SmartQueue",
        },
    )


def _fallback_classify(text: str, customer_tier: str = "standard") -> dict:
    """Keyword-based fallback when LLM is unavailable."""
    t = text.lower()
    if any(w in t for w in ("critical", "down", "outage", "breach", "compromised", "payment", "ransomware")):
        priority, category, sla, minutes, tier_r = 1, "outage" if "down" in t or "outage" in t else "security", 1, 30, "security_team" if "breach" in t or "compromised" in t else "tier1"
    elif any(w in t for w in ("slow", "broken", "sso", "login", "export", "rate limit", "double charge", "invoice", "billing")):
        priority, category, sla, minutes, tier_r = 2, "billing" if any(w in t for w in ("charge", "invoice", "billing", "refund")) else "technical", 4, 60, "billing_team" if any(w in t for w in ("charge", "invoice", "billing", "refund")) else "tier1"
    elif any(w in t for w in ("notification", "crash", "import", "spam", "locked", "access", "password", "2fa", "vpn")):
        priority, category, sla, minutes, tier_r = 3, "access" if any(w in t for w in ("locked", "access", "password", "vpn")) else "technical", 8, 120, "tier2"
    else:
        priority, category, sla, minutes, tier_r = 4, "feature", 48, 240, "engineering"
    tier_map = {"enterprise": tier_r, "standard": "tier2" if tier_r == "tier1" and priority > 1 else tier_r, "free": "tier2"}
    summary = " ".join(text.split()[:8])
    return {"category": category, "priority": priority, "tier": tier_map.get(customer_tier, tier_r),
            "sla_hours": sla, "estimated_minutes": minutes, "summary": summary, "tags": [category]}


async def classify_ticket(text: str, customer_tier: str = "standard") -> dict:
    try:
        prompt = _PROMPT.format(text=text[:1000], tier=customer_tier)
        resp = await _llm().chat.completions.create(
            model=_CLASSIFY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=250,
            timeout=10.0,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as exc:
        print(f"[classifier] LLM unavailable, using fallback: {exc}")
        return _fallback_classify(text, customer_tier)
