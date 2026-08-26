"""
Redis 缓存工具模块

Cache-Aside 模式：
- 读：先查 Redis → 未命中则查 DB → 写入 Redis
- 写：更新 DB → 删除 Redis 缓存

Redis 不可用时的降级策略：
- 首次请求 PING Redis（0.5s 超时）
- PING 失败 → 标记不可用 → 30 秒内所有请求零开销跳过 Redis
- 30 秒后自动重试 PING，Redis 恢复即切回缓存模式
"""

import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from src.config import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

logger = logging.getLogger(__name__)

# 异步 Redis 连接池（全局单例）
_redis_pool: aioredis.Redis | None = None

# 健康检查状态
_redis_available: bool | None = None   # None=未检查, True=可用, False=不可用
_last_ping_time: float = 0
PING_INTERVAL = 15  # Redis 不可用时，每 15 秒重试一次 PING


async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接（懒加载 + 短超时）"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            decode_responses=True,
            socket_connect_timeout=0.5,
        )
    return _redis_pool


# ── 缓存 Key 前缀 ──
KEY_PREFIX = "maoliao:"


def _cache_key(key: str) -> str:
    return f"{KEY_PREFIX}{key}"


async def _health_check() -> bool:
    """
    检查 Redis 是否可用。

    策略：
    - 首次调用：PING 一次（0.5s 超时）
    - PING 失败 → 标记不可用，30 秒内不再尝试
    - 30 秒后自动重试，成功则立即恢复
    """
    global _redis_available, _last_ping_time

    # Redis 已知不可用且未到重试时间 → 直接返回
    if _redis_available is False and time.time() - _last_ping_time < PING_INTERVAL:
        return False

    _last_ping_time = time.time()
    try:
        r = await get_redis()
        await r.ping()
        _set_available()
        return True
    except RedisError as e:
        _set_unavailable(e)
        return False


def _set_available() -> None:
    """标记 Redis 可用"""
    global _redis_available
    if _redis_available is not True:
        _redis_available = True
        logger.info("Redis 已连接，缓存功能正常")


def _set_unavailable(e: RedisError) -> None:
    """标记 Redis 不可用（首次打印警告，后续 30 秒内静默）"""
    global _redis_available
    if _redis_available is not False:
        _redis_available = False
        logger.warning(f"Redis 不可用，降级到纯数据库模式（每 {PING_INTERVAL}s 自动重试）: {e}")


async def cache_get(key: str) -> Any | None:
    """从 Redis 读取 JSON，未命中或 Redis 不可用返回 None"""
    if not await _health_check():
        return None
    try:
        r = await get_redis()
        data = await r.get(_cache_key(key))
        if data is None:
            return None
        return json.loads(data)
    except RedisError:
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """写入 Redis，Redis 不可用时静默跳过"""
    if not await _health_check():
        return
    try:
        r = await get_redis()
        await r.setex(_cache_key(key), ttl, json.dumps(value, ensure_ascii=False, default=str))
    except RedisError:
        pass


async def cache_delete(key: str) -> None:
    """删除 Redis 缓存，Redis 不可用时静默跳过"""
    if not await _health_check():
        return
    try:
        r = await get_redis()
        await r.delete(_cache_key(key))
    except RedisError:
        pass


async def cache_delete_pattern(pattern: str) -> None:
    """按通配符批量删除缓存，Redis 不可用时静默跳过"""
    if not await _health_check():
        return
    try:
        r = await get_redis()
        full_pattern = _cache_key(pattern)
        keys = await r.keys(full_pattern)
        if keys:
            await r.delete(*keys)
    except RedisError:
        pass
