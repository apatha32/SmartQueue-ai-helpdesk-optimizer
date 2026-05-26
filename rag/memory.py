import json
import os
from typing import Dict, List, Optional

import redis.asyncio as aioredis

_redis: Optional[aioredis.Redis] = None
_HISTORY_TTL = 3600  # seconds — sessions expire after 1 hour of inactivity
_MAX_TURNS = 20


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        addr = os.getenv("REDIS_ADDR", "localhost:6379")
        _redis = aioredis.from_url(f"redis://{addr}", decode_responses=True)
    return _redis


async def get_history(session_id: str) -> List[Dict]:
    """Return the last MAX_TURNS turns for the session as a list of {user, assistant} dicts."""
    r = await _get_redis()
    key = f"rag:session:{session_id}:history"
    raw = await r.lrange(key, -_MAX_TURNS, -1)
    history = []
    for item in raw:
        try:
            history.append(json.loads(item))
        except json.JSONDecodeError:
            pass
    return history


async def add_to_history(session_id: str, user_msg: str, assistant_msg: str) -> None:
    """Append one turn, keeping only the last MAX_TURNS turns."""
    if not assistant_msg:
        return
    r = await _get_redis()
    key = f"rag:session:{session_id}:history"
    turn = json.dumps({"user": user_msg, "assistant": assistant_msg})
    pipe = r.pipeline()
    pipe.rpush(key, turn)
    pipe.ltrim(key, -_MAX_TURNS, -1)
    pipe.expire(key, _HISTORY_TTL)
    await pipe.execute()
