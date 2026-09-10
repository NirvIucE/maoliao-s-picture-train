"""
Redis 缓存工具模块

Cache-Aside 模式：
- 读：先查 Redis → 未命中则查 DB → 写入 Redis
- 写：更新 DB → 删除 Redis 缓存

健康检查采用时间窗节流（P1-2）：
- 状态未知时 PING Redis（0.5s 超时）
- 已知可用 → 30 秒内不再 PING，直接用缓存
- PING 失败 → 标记不可用 → 15 秒内所有请求零开销跳过 Redis
- 窗口过后自动重试 PING，Redis 恢复即切回缓存模式
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
HEALTHY_PING_INTERVAL = 30  # Redis 已知可用时，30 秒内不重复 PING（P1-2 治理）

# SCAN 游标遍历的每批条数（P1-1 治理：替代 KEYS 全库扫描）
SCAN_BATCH = 100


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
            # 7.1 优化项：keepalive + 空闲健康检查，减少连接建立/断连抖动
            socket_keepalive=True,
            health_check_interval=30,
        )
    return _redis_pool


async def init_redis() -> bool:
    """应用启动时预热 Redis 连接（幂等，失败自动降级，绝不阻塞启动）"""
    try:
        ok = await _health_check()
        if ok:
            logger.info("Redis 连接预热完成")
        return ok
    except Exception as e:  # 预热失败仅记录，不影响应用启动
        _set_unavailable(e)
        return False


# ── 缓存 Key 前缀 ──
KEY_PREFIX = "maoliao:"


def _cache_key(key: str) -> str:
    return f"{KEY_PREFIX}{key}"


async def _health_check() -> bool:
    """
    检查 Redis 是否可用。

    策略（时间窗节流，P1-2 治理）：
    - 状态未知（None）：PING 一次（0.5s 超时）
    - PING 失败 → 标记不可用，PING_INTERVAL 内直接返回 False
    - 已知可用 → HEALTHY_PING_INTERVAL 内直接返回 True，不再 PING
      （原实现每次缓存操作都 PING，等于双倍往返）
    - 窗口过后自动重试 PING，成功则立即恢复
    """
    global _redis_available, _last_ping_time

    now = time.time()
    if _redis_available is not None:
        interval = HEALTHY_PING_INTERVAL if _redis_available else PING_INTERVAL
        if now - _last_ping_time < interval:
            return _redis_available

    _last_ping_time = now
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
        await r.set(_cache_key(key), json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
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
    """按通配符批量删除缓存，Redis 不可用时静默跳过

    用 SCAN 游标遍历（scan_iter）替代 KEYS：KEYS 是 O(N) 全库扫描，
    在 Redis 单线程模型下会阻塞所有其它命令（P1-1）。

    注意：必须「先收集完再删」。若在遍历过程中删除，哈希表收缩会让游标
    跳过尚未返回的 key（实测会漏删），因此删除动作放在遍历结束之后，
    再按 SCAN_BATCH 分块下发 DEL，避免单条命令参数过多。
    """
    if not await _health_check():
        return
    try:
        r = await get_redis()
        full_pattern = _cache_key(pattern)
        keys: list[str] = []
        async for key in r.scan_iter(match=full_pattern, count=SCAN_BATCH):
            keys.append(key)
        for i in range(0, len(keys), SCAN_BATCH):
            await r.delete(*keys[i : i + SCAN_BATCH])
    except RedisError:
        pass
