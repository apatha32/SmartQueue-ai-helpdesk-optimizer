"""Worker AI assistant — streams resolution guidance via OpenRouter + knowledge base."""
import os
from typing import AsyncGenerator

from classifier import _llm
from knowledge import search_knowledge

# Groq model for fast streaming chat; falls back to OpenRouter DeepSeek
_BOT_MODEL = os.getenv(
    "BOT_MODEL",
    "llama-3.3-70b-versatile" if os.getenv("GROQ_API_KEY") else "deepseek/deepseek-r1:free",
)

_SYSTEM = """\
You are SmartQueue Bot, an AI assistant helping IT support workers resolve tickets \
quickly and accurately. You have access to internal runbooks shown below.

Be concise, step-by-step, and practical. If you are unsure, say so — do not guess.

Current ticket:
Category : {category}
Priority : P{priority}
Summary  : {summary}
Description: {description}

Relevant runbook excerpts:
{knowledge}"""


def _static_fallback(message: str, ticket: dict, docs: list[dict]) -> str:
    """Rule-based response when the LLM is unavailable."""
    category = ticket.get("category", "") or ticket.get("payload", {}).get("category", "")
    summary  = ticket.get("summary",  "") or ticket.get("payload", {}).get("summary",  "")

    runbook = ""
    if docs:
        runbook = f"\n\nRunbook excerpt — {docs[0]['source']}:\n{docs[0]['content'][:400]}"

    intro = f"Regarding **{summary or message[:60]}**:" if (summary or message) else "Here is some guidance:"

    steps = {
        "outage":   "1. Check service status page\n2. Restart affected service\n3. Review recent deployments\n4. Escalate to on-call if not resolved in 15 min",
        "security": "1. Isolate affected system immediately\n2. Preserve logs\n3. Notify security team\n4. Follow incident response playbook",
        "access":   "1. Verify user identity\n2. Check group memberships in AD/LDAP\n3. Reset credentials if needed\n4. Confirm access after 5 min",
        "billing":  "1. Gather account and transaction details\n2. Check billing portal for errors\n3. Escalate to billing_team if unresolved",
        "technical":"1. Reproduce the issue\n2. Check recent changes (updates, config drift)\n3. Review error logs\n4. Apply known fix or escalate to tier2",
    }.get(category, "1. Gather full details from the user\n2. Check logs and recent changes\n3. Apply standard troubleshooting steps\n4. Escalate if unresolved after 30 min")

    return f"{intro}\n\n{steps}{runbook}\n\n*(AI LLM unavailable — rule-based guidance shown. Add a GROQ_API_KEY secret in Space settings for full AI responses.)*"


async def stream_bot_response(
    message: str,
    ticket: dict,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    try:
        docs = await search_knowledge(message, k=4)
    except Exception:
        docs = []
    knowledge_text = "\n\n".join(
        f"[{d['source']}]\n{d['content']}" for d in docs
    ) or "No specific runbook matched — apply general IT knowledge."

    system_content = _SYSTEM.format(
        category=ticket.get("category", ticket.get("payload", {}).get("category", "unknown")),
        priority=ticket.get("priority", "?"),
        summary=ticket.get("summary", ticket.get("payload", {}).get("summary", "N/A")),
        description=ticket.get("description", ticket.get("text", ticket.get("payload", {}).get("text", "N/A")))[:500],
        knowledge=knowledge_text,
    )

    messages = [{"role": "system", "content": system_content}]
    for turn in history[-10:]:
        messages.append(turn)
    messages.append({"role": "user", "content": message})

    try:
        stream = await _llm().chat.completions.create(
            model=_BOT_MODEL,
            messages=messages,
            stream=True,
            max_tokens=800,
            temperature=0.2,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception:
        # LLM unavailable — stream a rule-based fallback response
        response = _static_fallback(message, ticket, docs)
        for word in response.split(" "):
            yield word + " "
