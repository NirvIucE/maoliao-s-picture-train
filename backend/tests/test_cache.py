"""cache 模块降级测试：Redis 不可用时静默跳过，不阻塞业务（见计划 7.1 节）

覆盖 cache.py 未覆盖的降级路径（原 65% → 目标 90%+）：
- _health_check PING 失败 → 标记不可用
- _health_check 已知不可用 → 跳过重试
- cache_get/set/delete/delete_pattern 在 Redis 不可用时静默返回
- cache_get/set/delete/delete_pattern 在操作时 RedisError 被捕获
- API 层面：Redis 挂了，图片列表仍能从 DB 返回（降级到纯数据库模式）
"""

import time

import pytest
from redis.exceptions import RedisError

import src.cache as cache


class _DeadRedis:
    """模拟 Redis 完全不可用：ping 抛 RedisError"""

    async def ping(self):
        raise RedisError("connection refused")


class _BrokenRedis:
    """模拟操作中断开：ping 成功但 get/set/delete/keys 抛 RedisError"""

    async def ping(self):
        return True

    async def get(self, key):
        raise RedisError("connection lost during get")

    async def set(self, key, value, ex=None):
        raise RedisError("connection lost during set")

    async def delete(self, *keys):
        raise RedisError("connection lost during delete")

    async def keys(self, pattern):
        raise RedisError("connection lost during keys")


@pytest.fixture(autouse=True)
def reset_cache():
    """每个测试前后重置 cache 全局状态，保证隔离"""
    cache._redis_pool = None
    cache._redis_available = None
    cache._last_ping_time = 0
    yield
    cache._redis_pool = None
    cache._redis_available = None
    cache._last_ping_time = 0


class TestHealthCheck:
    async def test_ping_fails_marks_unavailable(self):
        """PING 失败 → _health_check 返回 False + _redis_available=False"""
        cache._redis_pool = _DeadRedis()
        result = await cache._health_check()
        assert result is False
        assert cache._redis_available is False

    async def test_skips_when_already_unavailable(self):
        """已知不可用 + PING_INTERVAL 内 → 直接返回 False，不重试"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        cache._redis_pool = _DeadRedis()  # 即使 ping 会抛异常也不会被调用
        result = await cache._health_check()
        assert result is False

    async def test_ping_succeeds_marks_available(self):
        """PING 成功 → _health_check 返回 True + _redis_available=True"""
        cache._redis_pool = _BrokenRedis()  # ping 成功
        result = await cache._health_check()
        assert result is True
        assert cache._redis_available is True


class TestCacheGet:
    async def test_returns_none_when_redis_down(self):
        """Redis 不可用时 cache_get → None（不崩，降级到 DB）"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        result = await cache.cache_get("any_key")
        assert result is None

    async def test_catches_redis_error(self):
        """health check 通过但 get() 抛 RedisError → 返回 None"""
        cache._redis_pool = _BrokenRedis()  # ping OK, get raises
        result = await cache.cache_get("any_key")
        assert result is None


class TestCacheSet:
    async def test_skips_when_redis_down(self):
        """Redis 不可用时 cache_set → 静默跳过（不崩）"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        await cache.cache_set("key", {"data": 1})  # 不应抛异常

    async def test_catches_redis_error(self):
        """health check 通过但 set() 抛 RedisError → 静默跳过"""
        cache._redis_pool = _BrokenRedis()
        await cache.cache_set("key", {"data": 1})  # 不应抛异常


class TestCacheDelete:
    async def test_skips_when_redis_down(self):
        """Redis 不可用时 cache_delete → 静默跳过"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        await cache.cache_delete("key")

    async def test_catches_redis_error(self):
        """delete() 抛 RedisError → 静默跳过"""
        cache._redis_pool = _BrokenRedis()
        await cache.cache_delete("key")


class TestCacheDeletePattern:
    async def test_skips_when_redis_down(self):
        """Redis 不可用时 cache_delete_pattern → 静默跳过"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        await cache.cache_delete_pattern("images:*")

    async def test_catches_redis_error(self):
        """keys() 抛 RedisError → 静默跳过"""
        cache._redis_pool = _BrokenRedis()
        await cache.cache_delete_pattern("images:*")


class TestAPIFallback:
    def test_image_list_works_without_redis(self, client, auth_headers, test_image):
        """Redis 挂了，图片列表接口仍能从 DB 返回 → 200 + total>=1"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        r = client.get("/api/images", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1  # 缓存 miss → 直接查 DB，数据仍在
