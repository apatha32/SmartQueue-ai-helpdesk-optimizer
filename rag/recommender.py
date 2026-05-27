"""Workload recommendation engine — tells the team what to do when tasks pile up."""
import json
import os

from classifier import _llm  # reuse same OpenRouter client

_RECOMMEND_MODEL = os.getenv("RECOMMEND_MODEL", "llama-3.3-70b-versatile")

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


def _rule_based_recommendations(queue_stats: dict) -> dict:
    """Fallback when LLM is unavailable — pure rule-based analysis."""
    pending    = queue_stats.get("pending_count", 0)
    processing = queue_stats.get("processing_count", 0)
    dead       = queue_stats.get("dead_count", 0)
    total      = queue_stats.get("total_jobs", pending + processing)

    recs = []
    score = 100

    if dead > 0:
        score -= min(30, dead * 5)
        recs.append({"action": "ALERT", "urgency": "immediate",
                     "detail": f"{dead} job(s) in dead-letter queue — review errors and retry.",
                     "affected_count": dead})

    if pending > 20:
        score -= 20
        recs.append({"action": "REASSIGN", "urgency": "soon",
                     "detail": f"Queue backlog of {pending} pending jobs — consider scaling workers.",
                     "affected_count": pending})
    elif pending > 5:
        score -= 10
        recs.append({"action": "BATCH", "urgency": "when_possible",
                     "detail": f"{pending} tickets pending — batch similar P3/P4 items to reduce load.",
                     "affected_count": pending})

    if processing > 10:
        score -= 15
        recs.append({"action": "ALERT", "urgency": "soon",
                     "detail": f"{processing} jobs in flight simultaneously — monitor for stalls.",
                     "affected_count": processing})

    if score == 100 and total == 0:
        summary = "Queue is idle — no active work items."
    elif score >= 80:
        summary = f"Queue is healthy with {pending} pending and {processing} processing."
    elif score >= 50:
        summary = f"Moderate load: {pending} pending, {processing} processing, {dead} dead."
    else:
        summary = f"Queue needs attention: {dead} dead jobs, {pending} pending backlog."

    if not recs:
        recs.append({"action": "DEFER", "urgency": "when_possible",
                     "detail": "No immediate action needed — queue is operating normally.",
                     "affected_count": 0})

    return {"health_score": max(0, score), "summary": summary, "recommendations": recs}


async def get_recommendations(queue_stats: dict) -> dict:
    try:
        summary = json.dumps(queue_stats, indent=2)
        resp = await _llm().chat.completions.create(
            model=_RECOMMEND_MODEL,
            messages=[{"role": "user", "content": _PROMPT.format(queue_summary=summary)}],
            temperature=0.3,
            max_tokens=600,
            timeout=10.0,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as exc:
        print(f"[recommender] LLM unavailable, using rule-based fallback: {exc}")
        return _rule_based_recommendations(queue_stats)
