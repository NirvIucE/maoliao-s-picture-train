"""cache 模块降级测试：Redis 不可用时静默跳过，不阻塞业务（见计划 7.1 节）

覆盖 cache.py 未覆盖的降级路径（原 65% → 目标 90%+）：
- _health_check PING 失败 → 标记不可用
- _health_check 已知不可用 → 跳过重试
- _health_check 已知可用 → 时间窗内不重复 PING（P1-2）
- cache_delete_pattern 走 SCAN 游标分批删除，只删匹配 key（P1-1）
- cache_get/set/delete/delete_pattern 在 Redis 不可用时静默返回
- cache_get/set/delete/delete_pattern 在操作时 RedisError 被捕获
- API 层面：Redis 挂了，图片列表仍能从 DB 返回（降级到纯数据库模式）
"""

import time

import fakeredis.aioredis
import pytest
from redis.exceptions import RedisError

import src.cache as cache


class _DeadRedis:
    """模拟 Redis 完全不可用：ping 抛 RedisError"""

    async def ping(self):
        raise RedisError("connection refused")


class _BrokenRedis:
    """模拟操作中断开：ping 成功但 get/set/delete/scan_iter 抛 RedisError"""

    async def ping(self):
        return True

    async def get(self, key):
        raise RedisError("connection lost during get")

    async def set(self, key, value, ex=None):
        raise RedisError("connection lost during set")

    async def delete(self, *keys):
        raise RedisError("connection lost during delete")

    async def scan_iter(self, match=None, count=None):
        """scan_iter 是异步生成器：首个 __anext__ 时抛错，被 except RedisError 捕获"""
        raise RedisError("connection lost during scan")
        yield  # pragma: no cover


class _CountingRedis:
    """只统计 ping 次数（验证健康检查节流），不参与数据操作"""

    def __init__(self):
        self.ping_count = 0

    async def ping(self):
        self.ping_count += 1
        return True


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
        """scan_iter() 抛 RedisError → 静默跳过"""
        cache._redis_pool = _BrokenRedis()
        await cache.cache_delete_pattern("images:*")


class TestHealthCheckThrottle:
    """P1-2 治理：已知可用时 30 秒内不重复 PING（原实现每次缓存操作都 PING）"""

    async def test_healthy_state_skips_repeated_ping(self):
        fake = _CountingRedis()
        cache._redis_pool = fake

        assert await cache._health_check() is True
        assert fake.ping_count == 1

        # 窗口内连续调用：不应产生任何额外 PING
        assert await cache._health_check() is True
        assert await cache._health_check() is True
        assert fake.ping_count == 1

        # 窗口过期 → 重新 PING
        cache._last_ping_time = time.time() - cache.HEALTHY_PING_INTERVAL - 1
        assert await cache._health_check() is True
        assert fake.ping_count == 2


class TestCacheDeletePatternScan:
    """P1-1 治理：SCAN 游标遍历替代 KEYS 全库扫描"""

    async def test_deletes_only_matched_keys(self):
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache._redis_pool = fake
        await fake.set("maoliao:images:user:1:a", "1")
        await fake.set("maoliao:images:user:1:b", "2")
        await fake.set("maoliao:images:user:2:c", "3")
        await fake.set("maoliao:other", "4")

        await cache.cache_delete_pattern("images:user:1:*")

        assert sorted(await fake.keys("maoliao:*")) == [
            "maoliao:images:user:2:c",
            "maoliao:other",
        ]

    async def test_batched_delete_flushes_all(self, monkeypatch):
        """key 数超过 SCAN_BATCH 时分块删除，一块都不漏

        回归保护：早期实现在遍历中删除，哈希表收缩导致游标跳过未返回的 key
        （本用例实测漏删 images:user:1:2），故删除必须发生在遍历结束之后。
        """
        monkeypatch.setattr(cache, "SCAN_BATCH", 2)
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache._redis_pool = fake
        for i in range(5):
            await fake.set(f"maoliao:images:user:1:{i}", str(i))
        await fake.set("maoliao:images:user:2:keep", "x")

        await cache.cache_delete_pattern("images:user:1:*")

        assert sorted(await fake.keys("maoliao:*")) == ["maoliao:images:user:2:keep"]


class TestAPIFallback:
    def test_image_list_works_without_redis(self, client, auth_headers, test_image):
        """Redis 挂了，图片列表接口仍能从 DB 返回 → 200 + total>=1"""
        cache._redis_available = False
        cache._last_ping_time = time.time()
        r = client.get("/api/images", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1  # 缓存 miss → 直接查 DB，数据仍在
