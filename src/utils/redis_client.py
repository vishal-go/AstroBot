"""Redis helper client for storing pending requests and tokens.

Uses `redis.asyncio` (the modern redis-py async client) instead of the legacy
`aioredis` package which can cause conflicts in some environments. The class
maintains the same async methods used by the bot and worker.
"""
from typing import Optional
import asyncio
import redis.asyncio as redis_async
from config import Config
from src.utils.logger import logger as log


class RedisClient:
    """Async Redis client wrapper for task coordination."""

    def __init__(self, redis: redis_async.Redis):
        self._redis = redis

    @classmethod
    async def create(cls):
        """Create and initialize Redis client.

        This uses `redis.asyncio.from_url` and returns a `RedisClient` wrapper.
        """
        url = Config.REDIS_URL or ""
        # If user provided host:port without scheme, prefix redis://
        if url and not (url.startswith("redis://") or url.startswith("rediss://") or url.startswith("unix://")):
            log.info("Normalizing REDIS_URL by adding redis:// scheme")
            url = f"redis://{url}"

        try:
            redis = redis_async.from_url(url or "redis://localhost:6379/0", decode_responses=True)
            await redis.ping()
            log.info("Connected to Redis")
            return cls(redis)
        except Exception as e:
            log.error(f"Failed to connect to Redis using URL '{url}': {e}")
            raise

    async def set_pending(self, correlation_id: str, payload: str, ttl: int = 300):
        """Store a pending payload and set a TTL."""
        await self._redis.hset(
            f"task:{correlation_id}",
            mapping={
                "status": "pending",
                "payload": payload,
                "created_at": str(asyncio.get_event_loop().time()),
            },
        )
        await self._redis.expire(f"task:{correlation_id}", ttl)

    async def set_working(self, correlation_id: str):
        """Mark task as being processed."""
        await self._redis.hset(f"task:{correlation_id}", "status", "working")

    async def set_result(self, correlation_id: str, result: str):
        """Store the completed result and mark status completed."""
        await self._redis.hset(
            f"task:{correlation_id}",
            mapping={
                "status": "completed",
                "result": result,
                "completed_at": str(asyncio.get_event_loop().time()),
            },
        )
        # Keep completed tasks for shorter time
        await self._redis.expire(f"task:{correlation_id}", 60)

    async def get_status(self, correlation_id: str) -> Optional[str]:
        """Return status (pending/working/completed) or None."""
        return await self._redis.hget(f"task:{correlation_id}", "status")

    async def get_result(self, correlation_id: str) -> Optional[str]:
        """Return result if available, else None."""
        return await self._redis.hget(f"task:{correlation_id}", "result")

    async def get_payload(self, correlation_id: str) -> Optional[str]:
        """Return original task payload."""
        return await self._redis.hget(f"task:{correlation_id}", "payload")

    async def cleanup_task(self, correlation_id: str):
        """Remove task from Redis."""
        await self._redis.delete(f"task:{correlation_id}")

    async def store_token(self, user_id: str, token: str, ttl: int = 3600):
        """Store a short-lived token for a user."""
        await self._redis.setex(f"token:{user_id}", ttl, token)

    async def get_token(self, user_id: str) -> Optional[str]:
        return await self._redis.get(f"token:{user_id}")
    
    async def is_pending(self, correlation_id: str) -> bool:
        """Check if a task is still pending."""
        status = await self.get_status(correlation_id)
        return status == "pending"
    
    async def set_attr(self, key: str, field: str, value: str):
        """Set a hash field to a value."""
        await self._redis.hset(key, field, value)
    
    async def get_attr(self, key: str, field: str) -> Optional[str]:
        """Get a hash field value."""
        return await self._redis.hget(key, field)
    