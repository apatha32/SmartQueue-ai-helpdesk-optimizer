"""
LangGraph ReAct agent with HyDE (Hypothetical Document Embeddings) query rewriting.

Flow per request:
  1. Load 20-turn session history from Redis.
  2. HyDE: ask the LLM to write a hypothetical answer → use that for dense retrieval.
  3. ReAct agent reasons with `retrieve_documents` tool backed by hybrid retrieval.
  4. Stream tokens back to the caller; emit final retrieved contexts at end.
"""

import os
from functools import lru_cache
from typing import AsyncGenerator, List, Optional, Tuple

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from memory import add_to_history, get_history
from retriever import hybrid_retrieve_rerank

_SYSTEM_PROMPT = (
    "You are a knowledgeable AI assistant with access to a document knowledge base. "
    "Always call the retrieve_documents tool before answering factual questions. "
    "Ground every answer in retrieved context. "
    "If the knowledge base has no relevant information, say so clearly and answer from general knowledge."
)


@lru_cache(maxsize=1)
def _llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        streaming=True,
    )


async def _hyde_expand(query: str) -> str:
    """Generate a hypothetical passage that would answer the query (HyDE technique)."""
    prompt = (
        "Write a short, factual passage that directly answers the following question. "
        "Be concise and information-dense. Do not add caveats.\n\n"
        f"Question: {query}"
    )
    response = await _llm().ainvoke([HumanMessage(content=prompt)])
    return response.content


@tool
async def retrieve_documents(query: str) -> str:
    """Search the knowledge base for documents relevant to the query.
    Always call this tool before answering factual questions."""
    hyde_text = await _hyde_expand(query)
    docs = await hybrid_retrieve_rerank(query, hyde_text=hyde_text)
    if not docs:
        return "No relevant documents found in the knowledge base."
    return "\n\n---\n\n".join(
        f"[Document {i + 1}]\n{doc.page_content}" for i, doc in enumerate(docs)
    )


def _build_agent():
    return create_react_agent(_llm(), [retrieve_documents])


_agent = _build_agent()


async def run_agent(
    message: str,
    session_id: str,
) -> AsyncGenerator[Tuple[str, Optional[List[str]]], None]:
    """
    Async generator that yields:
      - (token_chunk, None)  for each streamed token
      - ("", contexts)       once at the end with the list of retrieved context strings
    """
    history = await get_history(session_id)

    messages = [SystemMessage(content=_SYSTEM_PROMPT)]
    for turn in history:
        messages.append(HumanMessage(content=turn["user"]))
        messages.append(AIMessage(content=turn["assistant"]))
    messages.append(HumanMessage(content=message))

    full_response = ""
    retrieved_contexts: List[str] = []

    try:
        async for event in _agent.astream_events({"messages": messages}, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"].content
                if chunk:
                    full_response += chunk
                    yield chunk, None

            elif kind == "on_tool_end" and event.get("name") == "retrieve_documents":
                output = event["data"].get("output", "")
                if output and "No relevant documents" not in output:
                    retrieved_contexts.append(output)

    finally:
        await add_to_history(session_id, message, full_response)

    yield "", retrieved_contexts
