"""Redis 客户端单例

提供全局 Redis 连接，用于分布式锁、幂等 Token 等需要原生 Redis 命令的场景。

依据 DATABASE.md 第八部分 Redis 设计：
- 分布式锁使用 SET NX EX
- 幂等 Token 使用 SET NX EX + DEL
- 业务缓存使用 Django CACHES（django.core.cache.backends.redis.RedisCache）
"""
from __future__ import annotations

import threading

import redis
from django.conf import settings
from django.core.cache import cache as django_cache

# 模块级单例：复用连接池，避免每次调用创建新客户端
_redis_client: redis.Redis | None = None
_redis_lock = threading.Lock()


def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端单例

    使用 Django settings 中的 REDIS_HOST/PORT/PASSWORD/DB 配置。
    通过 decode_responses=True 自动解码为 str。

    首次调用创建客户端并复用底层连接池，后续调用直接返回同一实例。
    """
    global _redis_client
    if _redis_client is None:
        with _redis_lock:
            if _redis_client is None:
                _redis_client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=int(settings.REDIS_PORT),
                    password=settings.REDIS_PASSWORD or None,
                    db=int(settings.REDIS_DB),
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
    return _redis_client


def get_django_cache():
    """获取 Django 缓存后端（用于业务缓存 Cache-Aside / Write-Through）"""
    return django_cache
