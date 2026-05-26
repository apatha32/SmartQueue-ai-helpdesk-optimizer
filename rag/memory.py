"""Redis-backed 20-turn conversation memory for the AI bot."""
import json
import os
from typing import Any

import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None


async def _r() -> aioredis.Redis:
    global _redis
    if _redis is None:
        addr = os.getenv("REDIS_ADDR", "localhost:6379")
        host, port = addr.rsplit(":", 1)
        _redis = aioredis.Redis(host=host, port=int(port), decode_responses=True)
    return _redis


async def get_history(session_id: str) -> list[dict[str, Any]]:
    r = await _r()
    raw = await r.lrange(f"bot:session:{session_id}:history", -20, -1)
    msgs = []
    for item in raw:
        try:
            msgs.append(json.loads(item))
        except json.JSONDecodeError:
            pass
    return msgs


async def add_to_history(session_id: str, user_msg: str, assistant_msg: str) -> None:
    r = await _r()
    key = f"bot:session:{session_id}:history"
    pipe = r.pipeline()
    pipe.rpush(key, json.dumps({"role": "user", "content": user_msg}))
    pipe.rpush(key, json.dumps({"role": "assistant", "content": assistant_msg}))
    pipe.ltrim(key, -20, -1)
    pipe.expire(key, 3600)
    await pipe.execute()


async def clear_history(session_id: str) -> None:
    r = await _r()
    await r.delete(f"bot:session:{session_id}:history")
