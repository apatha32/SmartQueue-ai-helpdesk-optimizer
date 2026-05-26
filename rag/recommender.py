"""Workload recommendation engine — tells the team what to do when tasks pile up."""
import json
import os

from classifier import _llm  # reuse same OpenRouter client

_RECOMMEND_MODEL = os.getenv("RECOMMEND_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

_PROMPT = """\
You are an IT operations manager. Analyze the helpdesk queue state below and produce \
4 specific, actionable recommendations. Respond with a single JSON object only — \
no markdown, no extra text.

Queue state:
{queue_summary}

Rules:
- P1/P2 tickets with <25% SLA time remaining must be escalated immediately
- Group similar P3/P4 tickets for batch handling when possible
- Flag overloaded tiers and suggest redistribution
- Be specific: mention counts, categories, and tiers by name

JSON schema:
{{
  "health_score": <0-100>,
  "summary": "<one sentence assessment>",
  "recommendations": [
    {{
      "action": "ESCALATE|BATCH|DEFER|REASSIGN|ALERT",
      "urgency": "immediate|soon|when_possible",
      "detail": "<specific instruction>",
      "affected_count": <number>
    }}
  ]
}}"""


async def get_recommendations(queue_stats: dict) -> dict:
    summary = json.dumps(queue_stats, indent=2)
    resp = await _llm().chat.completions.create(
        model=_RECOMMEND_MODEL,
        messages=[{"role": "user", "content": _PROMPT.format(queue_summary=summary)}],
        temperature=0.3,
        max_tokens=600,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
