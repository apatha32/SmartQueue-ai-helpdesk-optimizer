import json
import logging
import os
from typing import List, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None
_EVAL_TTL = 3600


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        addr = os.getenv("REDIS_ADDR", "localhost:6379")
        _redis = aioredis.from_url(f"redis://{addr}", decode_responses=True)
    return _redis


async def evaluate_async(
    question: str,
    answer: str,
    contexts: List[str],
    session_id: str,
) -> None:
    """
    Run RAGAS evaluation metrics (answer relevancy, faithfulness, context recall)
    and persist results to Redis. Non-blocking — failures are logged and ignored.
    """
    if not contexts or not answer:
        return

    try:
        import os as _os
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import AnswerRelevancy, Faithfulness, ContextRecall
        from ragas.llms import LangchainLLMWrapper
        from langchain_anthropic import ChatAnthropic

        llm = LangchainLLMWrapper(
            ChatAnthropic(
                model="claude-sonnet-4-20250514",
                api_key=_os.getenv("ANTHROPIC_API_KEY"),
            )
        )

        dataset = Dataset.from_dict(
            {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
                "ground_truth": [answer],
            }
        )

        result = evaluate(
            dataset,
            metrics=[AnswerRelevancy(), Faithfulness(), ContextRecall()],
            llm=llm,
        )

        scores = {
            "answer_relevancy": round(float(result["answer_relevancy"]), 4),
            "faithfulness": round(float(result["faithfulness"]), 4),
            "context_recall": round(float(result["context_recall"]), 4),
            "question": question[:200],
        }

        r = await _get_redis()
        await r.setex(f"rag:eval:{session_id}", _EVAL_TTL, json.dumps(scores))

    except Exception as exc:
        logger.warning("RAGAS evaluation failed for session %s: %s", session_id, exc)


async def get_latest_eval(session_id: str) -> Optional[dict]:
    r = await _get_redis()
    raw = await r.get(f"rag:eval:{session_id}")
    if raw:
        return json.loads(raw)
    return None
