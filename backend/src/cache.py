"""
Redis 缓存工具模块

Cache-Aside 模式：
- 读：先查 Redis → 未命中则查 DB → 写入 Redis
- 写：更新 DB → 删除 Redis 缓存（下次读自动重新加载）
"""

import json
from typing import Any
import redis.asyncio as aioredis
from src.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

# 异步 Redis 连接池（全局单例）
_redis_pool: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接（懒加载 + 连接池复用）"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            decode_responses=True,   # 自动把 bytes → str
        )
    return _redis_pool


# ── 缓存 Key 前缀（防止和别的项目冲突） ──
KEY_PREFIX = "maoliao:"

def _cache_key(key: str) -> str:
    """给 key 加项目前缀，如 'user:5' → 'maoliao:user:5'"""
    return f"{KEY_PREFIX}{key}"

async def cache_get(key: str) -> Any | None:
    """从 Redis 读取 JSON，未命中返回 None"""
    r = await get_redis()
    data = await r.get(_cache_key(key))
    if data is None:
        return None
    return json.loads(data)

async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """写入 Redis（JSON 序列化 + 设置过期时间，默认 300 秒）"""
    r = await get_redis()
    await r.setex(_cache_key(key), ttl, json.dumps(value, ensure_ascii=False, default=str))

async def cache_delete(key: str) -> None:
    """删除 Redis 缓存"""
    r = await get_redis()
    await r.delete(_cache_key(key))

async def cache_delete_pattern(pattern: str) -> None:
    """按通配符批量删除缓存，如 'images:user:5:*'"""
    r = await get_redis()
    full_pattern = _cache_key(pattern)
    keys = await r.keys(full_pattern)
    if keys:
        await r.delete(*keys)