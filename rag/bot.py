"""Worker AI assistant — streams resolution guidance via OpenRouter + knowledge base."""
import os
from typing import AsyncGenerator

from classifier import _llm
from knowledge import search_knowledge

_BOT_MODEL = os.getenv("BOT_MODEL", "deepseek/deepseek-r1:free")

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


async def stream_bot_response(
    message: str,
    ticket: dict,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    docs = await search_knowledge(message, k=4)
    knowledge_text = "\n\n".join(
        f"[{d['source']}]\n{d['content']}" for d in docs
    ) or "No specific runbook matched — apply general IT knowledge."

    system_content = _SYSTEM.format(
        category=ticket.get("category", "unknown"),
        priority=ticket.get("priority", "?"),
        summary=ticket.get("summary", "N/A"),
        description=ticket.get("description", ticket.get("text", "N/A"))[:500],
        knowledge=knowledge_text,
    )

    messages = [{"role": "system", "content": system_content}]
    for turn in history[-10:]:
        messages.append(turn)
    messages.append({"role": "user", "content": message})

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
