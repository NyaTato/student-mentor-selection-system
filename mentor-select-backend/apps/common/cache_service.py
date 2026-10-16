"""缓存服务

实现 DATABASE.md 8.3 缓存策略：
- Write-Through：当前 ACTIVE 学年、系统状态、导入任务状态（写时同步更新）
- Cache-Aside：导师信息/名额、导师列表、公告列表（读时回填，写时删除）

一致性保障（DATABASE.md 8.5）：
1. 先更新 DB，再删除缓存（Cache-Aside）
2. Write-Through 保证强一致
3. 导师名额缓存仅用于读取展示，录取校验必须查 DB + 行锁
4. 缓存 miss 或不一致时，以 DB 为准
5. 学年切换时批量删除旧学年的所有缓存 Key

业务缓存使用 Django cache 后端（django.core.cache.backends.redis.RedisCache），
分布式锁和幂等 Token 使用原生 Redis 客户端（apps.common.redis_client）。
"""
from __future__ import annotations

import json
import random
import time
from typing import Any, Callable

from django.core.cache import cache

from apps.common.cache_keys import (
    TTL_ANNOUNCEMENT,
    TTL_IMPORT_TASK,
    TTL_NONE,
    TTL_TEACHER_INFO,
    TTL_TEACHER_LIST,
    all_year_patterns,
    announcement_published,
    import_task,
    state,
    teacher_info,
    teacher_list,
    teacher_quota,
    year_active,
)
from apps.common.logger import get_logger
from apps.common.redis_client import get_redis_client
from apps.monitoring.services import MetricsService

logger = get_logger("common.cache")

# 空值缓存标记，用于防缓存穿透
_CACHE_NULL_SENTINEL = "__MENTOR_SELECT_CACHE_NULL__"
# 空值缓存 TTL（秒）：短 TTL，防止穿透同时避免长期缓存空值
NULL_CACHE_TTL = 60


class CacheService:
    """缓存服务

    提供两类策略的统一接口：
    - Write-Through：write_through() — 同步写入缓存
    - Cache-Aside：get_or_set() — 读时回填；invalidate() — 写时删除

    所有方法自动处理序列化（JSON）和 Key 构建。
    Metrics 记录通过 MetricsService 调用，MetricsService 内部 @_safe 装饰器
    保证 metrics 失败不会抛出异常，因此本类无需额外 try/except 包装。
    """

    # ===== Write-Through（强一致场景） =====

    @classmethod
    def write_through(cls, key: str, data: Any, ttl: int | None = TTL_NONE) -> None:
        """Write-Through 写入缓存

        用于当前 ACTIVE 学年、系统状态、导入任务状态等强一致场景。
        在 DB 事务提交后调用。

        Args:
            key: 缓存 Key
            data: 可序列化的数据
            ttl: TTL（秒），None 表示不过期
        """
        start = time.perf_counter()
        success = False
        try:
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            cache.set(key, serialized, timeout=ttl)
            success = True
            logger.debug("Write-Through: key=%s", key)
        except Exception as exc:
            logger.error("Write-Through failed: key=%s, error=%s", key, exc)
        finally:
            MetricsService.record_cache_operation(
                "set", "success" if success else "fail",
                time.perf_counter() - start,
            )

    @classmethod
    def read_through(cls, key: str) -> Any | None:
        """读取 Write-Through 缓存

        Args:
            key: 缓存 Key

        Returns:
            反序列化后的数据，未命中返回 None
        """
        start = time.perf_counter()
        result_label = "miss"
        try:
            value = cache.get(key)
            if value is None:
                return None
            result_label = "hit"
            return json.loads(value)
        except Exception as exc:
            logger.error("Read-Through failed: key=%s, error=%s", key, exc)
            return None
        finally:
            MetricsService.record_cache_operation(
                "get", result_label, time.perf_counter() - start,
            )

    # ===== Cache-Aside（允许短暂不一致） =====

    @classmethod
    def get_or_set(
        cls,
        key: str,
        loader: Callable[[], Any],
        ttl: int | None = TTL_NONE,
    ) -> Any:
        """Cache-Aside 读取：缓存 miss 时从 loader 加载并回填

        用于导师信息/名额、导师列表、公告列表等高频读场景。

        Args:
            key: 缓存 Key
            loader: 缓存 miss 时的数据加载函数
            ttl: TTL（秒），None 表示不过期

        Returns:
            缓存或 loader 返回的数据
        """
        start = time.perf_counter()
        try:
            value = cache.get(key)
            if value is not None:
                decoded = json.loads(value)
                # 空值缓存命中（防穿透）：直接返回 None，不回源
                if decoded == _CACHE_NULL_SENTINEL:
                    logger.debug("Cache null hit: key=%s", key)
                    MetricsService.record_cache_operation(
                        "get", "hit", time.perf_counter() - start,
                    )
                    return None
                logger.debug("Cache hit: key=%s", key)
                MetricsService.record_cache_operation(
                    "get", "hit", time.perf_counter() - start,
                )
                return decoded
        except Exception as exc:
            logger.error("Cache read failed: key=%s, error=%s", key, exc)

        # Cache miss → 从 DB 加载
        logger.debug("Cache miss: key=%s", key)
        MetricsService.record_cache_operation(
            "get", "miss", time.perf_counter() - start,
        )

        data = loader()

        if data is None:
            # 缓存空值防穿透：短 TTL，避免恶意请求反复击穿到 DB
            MetricsService.record_cache_penetration()
            cls._set_cache(key, _CACHE_NULL_SENTINEL, NULL_CACHE_TTL)
        else:
            cls._set_cache(key, data, ttl)

        return data

    @classmethod
    def invalidate(cls, key: str) -> None:
        """删除缓存（Cache-Aside 写时删除）

        在 DB 更新后调用，删除对应缓存 Key。

        Args:
            key: 缓存 Key
        """
        start = time.perf_counter()
        success = False
        try:
            cache.delete(key)
            success = True
            logger.debug("Cache invalidated: key=%s", key)
        except Exception as exc:
            logger.error("Cache invalidate failed: key=%s, error=%s", key, exc)
        finally:
            MetricsService.record_cache_operation(
                "delete", "success" if success else "fail",
                time.perf_counter() - start,
            )

    @classmethod
    def invalidate_many(cls, keys: list[str]) -> None:
        """批量删除缓存

        Args:
            keys: 缓存 Key 列表
        """
        start = time.perf_counter()
        success = False
        try:
            cache.delete_many(keys)
            success = True
            logger.debug("Cache invalidated (batch): count=%d", len(keys))
        except Exception as exc:
            logger.error("Cache invalidate_many failed: error=%s", exc)
        finally:
            MetricsService.record_cache_operation(
                "delete", "success" if success else "fail",
                time.perf_counter() - start,
            )

    @classmethod
    def invalidate_year(cls, academic_year_id: int) -> None:
        """学年切换时批量删除该学年的所有缓存 Key

        依据 DATABASE.md 8.5 第 5 条：学年切换时必须批量删除旧学年的所有缓存 Key。

        注意：本方法直接调用 cache.delete_many 而非 cls.invalidate_many，
        避免与本方法的 delete metric 产生双重计数。

        Args:
            academic_year_id: 学年 ID
        """
        start = time.perf_counter()
        success = False
        try:
            client = get_redis_client()
            deleted_count = 0

            for pattern in all_year_patterns(academic_year_id):
                # SCAN 避免阻塞（不用 KEYS）
                for key in client.scan_iter(match=pattern, count=100):
                    client.delete(key)
                    deleted_count += 1

            # 同时删除 Django cache 中的 Key
            # 直接调用 cache.delete_many 而非 cls.invalidate_many，
            # 避免与本方法的 delete metric 产生双重计数
            keys_to_delete = [
                state(academic_year_id),
                teacher_list(academic_year_id),
                announcement_published(academic_year_id),
            ]
            cache.delete_many(keys_to_delete)

            logger.info(
                "Cache invalidated (year): academic_year_id=%d, deleted=%d",
                academic_year_id, deleted_count,
            )
            success = True
        except Exception as exc:
            logger.error(
                "Cache invalidate_year failed: year=%s, error=%s",
                academic_year_id, exc,
            )
        finally:
            MetricsService.record_cache_operation(
                "delete", "success" if success else "fail",
                time.perf_counter() - start,
            )

    # ===== 内部方法 =====

    @staticmethod
    def _jitter_ttl(ttl: int | None) -> int | None:
        """对 TTL 添加随机抖动，防缓存雪崩

        仅对 > 60 秒的 TTL 添加 0-20% 正向随机抖动，
        使同时写入的大量 key 在不同时刻过期，避免雪崩。
        """
        if ttl is None:
            return None
        if ttl <= 60:
            return ttl
        # 记录雪崩保护触发（TTL 抖动生效）
        MetricsService.record_cache_avalanche_protection()
        return int(ttl + random.uniform(0, ttl * 0.2))

    @classmethod
    def _set_cache(cls, key: str, data: Any, ttl: int | None) -> None:
        """写入缓存（内部方法）"""
        start = time.perf_counter()
        success = False
        try:
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            cache.set(key, serialized, timeout=cls._jitter_ttl(ttl))
            success = True
        except Exception as exc:
            logger.error("Cache set failed: key=%s, error=%s", key, exc)
        finally:
            MetricsService.record_cache_operation(
                "set", "success" if success else "fail",
                time.perf_counter() - start,
            )


# ===== 业务专用缓存方法 =====


class AcademicYearCache:
    """当前 ACTIVE 学年缓存（Write-Through）"""

    @staticmethod
    def set(year_data: dict) -> None:
        """学年切换时同步更新缓存"""
        CacheService.write_through(year_active(), year_data, TTL_NONE)

    @staticmethod
    def get() -> dict | None:
        return CacheService.read_through(year_active())

    @staticmethod
    def invalidate() -> None:
        CacheService.invalidate(year_active())


class SystemStateCache:
    """系统状态缓存（Write-Through）"""

    @staticmethod
    def set(academic_year_id: int, state_data: dict) -> None:
        CacheService.write_through(state(academic_year_id), state_data, TTL_NONE)

    @staticmethod
    def get(academic_year_id: int) -> dict | None:
        return CacheService.read_through(state(academic_year_id))

    @staticmethod
    def invalidate(academic_year_id: int) -> None:
        CacheService.invalidate(state(academic_year_id))


class TeacherInfoCache:
    """导师详情缓存（Cache-Aside，30 min TTL）"""

    @staticmethod
    def get_or_set(
        academic_year_id: int, teacher_id: int, loader: Callable[[], dict]
    ) -> dict:
        return CacheService.get_or_set(
            teacher_info(academic_year_id, teacher_id),
            loader,
            TTL_TEACHER_INFO,
        )

    @staticmethod
    def invalidate(academic_year_id: int, teacher_id: int) -> None:
        CacheService.invalidate(teacher_info(academic_year_id, teacher_id))


class TeacherQuotaCache:
    """导师剩余名额缓存（Cache-Aside，不过期，录取/撤销时删除）"""

    @staticmethod
    def get_or_set(
        academic_year_id: int, teacher_id: int, loader: Callable[[], dict]
    ) -> dict:
        return CacheService.get_or_set(
            teacher_quota(academic_year_id, teacher_id),
            loader,
            TTL_NONE,
        )

    @staticmethod
    def invalidate(academic_year_id: int, teacher_id: int) -> None:
        CacheService.invalidate(teacher_quota(academic_year_id, teacher_id))


class TeacherListCache:
    """导师列表缓存（Cache-Aside，10 min TTL）"""

    @staticmethod
    def get_or_set(
        academic_year_id: int, loader: Callable[[], list]
    ) -> list:
        return CacheService.get_or_set(
            teacher_list(academic_year_id),
            loader,
            TTL_TEACHER_LIST,
        )

    @staticmethod
    def invalidate(academic_year_id: int) -> None:
        CacheService.invalidate(teacher_list(academic_year_id))


class AnnouncementCache:
    """已发布公告列表缓存（Cache-Aside，5 min TTL）"""

    @staticmethod
    def get_or_set(
        academic_year_id: int, loader: Callable[[], list]
    ) -> list:
        return CacheService.get_or_set(
            announcement_published(academic_year_id),
            loader,
            TTL_ANNOUNCEMENT,
        )

    @staticmethod
    def invalidate(academic_year_id: int) -> None:
        CacheService.invalidate(announcement_published(academic_year_id))


class ImportTaskCache:
    """导入任务状态缓存（Write-Through，1 hour TTL）"""

    @staticmethod
    def set(task_id: int, task_data: dict) -> None:
        CacheService.write_through(import_task(task_id), task_data, TTL_IMPORT_TASK)

    @staticmethod
    def get(task_id: int) -> dict | None:
        return CacheService.read_through(import_task(task_id))

    @staticmethod
    def invalidate(task_id: int) -> None:
        CacheService.invalidate(import_task(task_id))


class DashboardCache:
    """Dashboard 缓存（Cache-Aside，5 min TTL）

    用于管理后台统计数据展示。
    """

    DASHBOARD_KEY_TEMPLATE = "dashboard:{academic_year_id}"

    @staticmethod
    def get_or_set(
        academic_year_id: int, loader: Callable[[], dict]
    ) -> dict:
        key = DashboardCache.DASHBOARD_KEY_TEMPLATE.format(academic_year_id=academic_year_id)
        return CacheService.get_or_set(key, loader, TTL_ANNOUNCEMENT)

    @staticmethod
    def invalidate(academic_year_id: int) -> None:
        key = DashboardCache.DASHBOARD_KEY_TEMPLATE.format(academic_year_id=academic_year_id)
        CacheService.invalidate(key)
