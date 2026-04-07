import json
from functools import wraps

from tg_bot import redis_client


def cached(ttl=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{json.dumps(args, default=str)}:{json.dumps(kwargs, default=str)}"

            loop = None
            try:
                import asyncio
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if loop is not None:
                return func(*args, **kwargs)

            return func(*args, **kwargs)

        return wrapper

    return decorator


async def clear_cache():
    await redis_client.flushdb()


async def invalidate_cache_pattern(pattern):
    async for key in redis_client.scan_iter(pattern):
        await redis_client.delete(key)
