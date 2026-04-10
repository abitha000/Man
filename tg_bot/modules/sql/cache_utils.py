from tg_bot import redis_client


async def clear_cache():
    await redis_client.flushdb()


async def invalidate_cache_pattern(pattern):
    async for key in redis_client.scan_iter(pattern):
        await redis_client.delete(key)
