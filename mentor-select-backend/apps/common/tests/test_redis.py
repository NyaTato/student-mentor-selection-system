"""Redis 缓存 + 分布式锁 + 幂等 Token 测试

使用 unittest.mock 模拟 Redis 客户端，避免依赖真实 Redis 服务。
测试覆盖：
- CacheService: Write-Through / Cache-Aside / 失效
- 业务缓存: AcademicYear / SystemState / TeacherInfo / TeacherList / Announcement / ImportTask / Dashboard
- DistributedLock: 获取 / 释放 / 上下文管理器
- IdempotentToken: 获取 / 重复检测 / 结果存储
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.common.cache_keys import (
    LOCK_TTL_AUTO_ASSIGN,
    LOCK_TTL_STATE_TRANSITION,
    TTL_IDEMPOTENT,
    TTL_IMPORT_TASK,
    TTL_TEACHER_INFO,
    idempotent,
    lock_auto_assign,
    lock_state_transition,
    state,
    teacher_info,
    teacher_list,
    year_active,
)
from apps.common.cache_service import (
    AcademicYearCache,
    AnnouncementCache,
    CacheService,
    DashboardCache,
    ImportTaskCache,
    SystemStateCache,
    TeacherInfoCache,
    TeacherListCache,
)
from apps.common.lock import (
    DistributedLock,
    IdempotentToken,
    LockAcquisitionError,
    acquire_lock,
    check_idempotent,
)


# ===== CacheService 测试 =====


@pytest.mark.django_db
class TestCacheService:
    """缓存服务测试"""

    def test_write_through_sets_cache(self):
        """Write-Through 写入缓存"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            CacheService.write_through("test:key", {"name": "测试"}, ttl=60)
            mock_cache.set.assert_called_once()
            args = mock_cache.set.call_args
            assert args[0][0] == "test:key"
            assert json.loads(args[0][1])["name"] == "测试"
            assert args[1]["timeout"] == 60

    def test_read_through_gets_cache(self):
        """Read-Through 读取缓存"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = json.dumps({"name": "测试"})
            result = CacheService.read_through("test:key")
            assert result["name"] == "测试"
            mock_cache.get.assert_called_once_with("test:key")

    def test_read_through_cache_miss(self):
        """Read-Through 缓存未命中"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            result = CacheService.read_through("test:key")
            assert result is None

    def test_get_or_set_cache_hit(self):
        """Cache-Aside 命中缓存"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = json.dumps({"name": "测试"})
            loader = MagicMock()
            result = CacheService.get_or_set("test:key", loader, ttl=60)
            assert result["name"] == "测试"
            loader.assert_not_called()  # 缓存命中，不调用 loader

    def test_get_or_set_cache_miss(self):
        """Cache-Aside 未命中，从 loader 加载"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            loader = MagicMock(return_value={"name": "从DB加载"})
            result = CacheService.get_or_set("test:key", loader, ttl=60)
            assert result["name"] == "从DB加载"
            loader.assert_called_once()
            mock_cache.set.assert_called_once()

    def test_invalidate(self):
        """删除缓存"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            CacheService.invalidate("test:key")
            mock_cache.delete.assert_called_once_with("test:key")

    def test_invalidate_many(self):
        """批量删除缓存"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            CacheService.invalidate_many(["key1", "key2"])
            mock_cache.delete_many.assert_called_once_with(["key1", "key2"])


# ===== 业务缓存测试 =====


@pytest.mark.django_db
class TestAcademicYearCache:
    """当前 ACTIVE 学年缓存测试"""

    def test_set(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            AcademicYearCache.set({"id": 1, "name": "2024-2025"})
            mock_cache.set.assert_called_once()
            args = mock_cache.set.call_args
            assert args[0][0] == year_active()

    def test_get(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = json.dumps({"id": 1})
            result = AcademicYearCache.get()
            assert result["id"] == 1

    def test_invalidate(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            AcademicYearCache.invalidate()
            mock_cache.delete.assert_called_once_with(year_active())


@pytest.mark.django_db
class TestSystemStateCache:
    """系统状态缓存测试"""

    def test_set(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            SystemStateCache.set(1, {"state": "selection"})
            mock_cache.set.assert_called_once()
            args = mock_cache.set.call_args
            assert args[0][0] == state(1)

    def test_get(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = json.dumps({"state": "selection"})
            result = SystemStateCache.get(1)
            assert result["state"] == "selection"

    def test_invalidate(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            SystemStateCache.invalidate(1)
            mock_cache.delete.assert_called_once_with(state(1))


@pytest.mark.django_db
class TestTeacherInfoCache:
    """导师详情缓存测试"""

    def test_get_or_set_cache_hit(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = json.dumps({"name": "张教授"})
            loader = MagicMock()
            result = TeacherInfoCache.get_or_set(1, 100, loader)
            assert result["name"] == "张教授"
            loader.assert_not_called()

    def test_get_or_set_cache_miss(self):
        """Cache-Aside 未命中，从 loader 加载"""
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            loader = MagicMock(return_value={"name": "张教授"})
            result = TeacherInfoCache.get_or_set(1, 100, loader)
            assert result["name"] == "张教授"
            loader.assert_called_once()
            # 验证 TTL 在 30 min 附近（含防雪崩随机抖动 0-20%）
            args = mock_cache.set.call_args
            timeout = args[1]["timeout"]
            assert TTL_TEACHER_INFO <= timeout <= int(TTL_TEACHER_INFO * 1.2)

    def test_invalidate(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            TeacherInfoCache.invalidate(1, 100)
            mock_cache.delete.assert_called_once_with(teacher_info(1, 100))


@pytest.mark.django_db
class TestTeacherListCache:
    """导师列表缓存测试"""

    def test_get_or_set(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            loader = MagicMock(return_value=[{"id": 1}, {"id": 2}])
            result = TeacherListCache.get_or_set(1, loader)
            assert len(result) == 2
            loader.assert_called_once()

    def test_invalidate(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            TeacherListCache.invalidate(1)
            mock_cache.delete.assert_called_once_with(teacher_list(1))


@pytest.mark.django_db
class TestAnnouncementCache:
    """公告列表缓存测试"""

    def test_get_or_set(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            loader = MagicMock(return_value=[{"id": 1, "title": "公告1"}])
            result = AnnouncementCache.get_or_set(1, loader)
            assert len(result) == 1
            loader.assert_called_once()

    def test_invalidate(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            AnnouncementCache.invalidate(1)
            mock_cache.delete.assert_called_once()


@pytest.mark.django_db
class TestImportTaskCache:
    """导入任务状态缓存测试"""

    def test_set(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            ImportTaskCache.set(1, {"status": "processing"})
            mock_cache.set.assert_called_once()
            args = mock_cache.set.call_args
            assert args[1]["timeout"] == TTL_IMPORT_TASK

    def test_get(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = json.dumps({"status": "success"})
            result = ImportTaskCache.get(1)
            assert result["status"] == "success"


@pytest.mark.django_db
class TestDashboardCache:
    """Dashboard 缓存测试"""

    def test_get_or_set(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            mock_cache.get.return_value = None
            loader = MagicMock(return_value={"total_students": 100})
            result = DashboardCache.get_or_set(1, loader)
            assert result["total_students"] == 100

    def test_invalidate(self):
        with patch("apps.common.cache_service.cache") as mock_cache:
            DashboardCache.invalidate(1)
            mock_cache.delete.assert_called_once()


# ===== 分布式锁测试 =====


@pytest.mark.django_db
class TestDistributedLock:
    """分布式锁测试"""

    def test_acquire_success(self):
        """获取锁成功"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_get_client.return_value = mock_client

            lock = DistributedLock("lock:test", ttl=10)
            assert lock.acquire() is True
            assert lock.is_acquired is True
            mock_client.set.assert_called_once()

    def test_acquire_failed(self):
        """获取锁失败（已被占用）"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = None
            mock_get_client.return_value = mock_client

            lock = DistributedLock("lock:test", ttl=10)
            assert lock.acquire() is False
            assert lock.is_acquired is False

    def test_release_success(self):
        """释放锁成功"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_client.eval.return_value = 1
            mock_get_client.return_value = mock_client

            lock = DistributedLock("lock:test", ttl=10)
            lock.acquire()
            assert lock.release() is True
            mock_client.eval.assert_called_once()

    def test_context_manager_success(self):
        """上下文管理器获取锁"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_client.eval.return_value = 1
            mock_get_client.return_value = mock_client

            with DistributedLock("lock:test", ttl=10) as acquired:
                assert acquired is True
                assert mock_client.set.called

    def test_context_manager_release_on_exit(self):
        """退出上下文自动释放"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_client.eval.return_value = 1
            mock_get_client.return_value = mock_client

            lock = DistributedLock("lock:test", ttl=10)
            with lock as acquired:
                assert acquired is True

            # 退出后应调用 eval 释放
            assert mock_client.eval.called

    def test_acquire_lock_helper_raises(self):
        """acquire_lock 便捷方法获取失败抛异常"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = None
            mock_get_client.return_value = mock_client

            with pytest.raises(LockAcquisitionError):
                with acquire_lock("lock:test", ttl=10, raise_on_fail=True):
                    pass

    def test_acquire_lock_helper_no_raise(self):
        """acquire_lock 便捷方法不抛异常"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = None
            mock_get_client.return_value = mock_client

            with acquire_lock("lock:test", ttl=10, raise_on_fail=False) as lock:
                assert lock.is_acquired is False

    def test_lock_key_builder(self):
        """验证锁 Key 构建器"""
        assert lock_state_transition(1) == "lock:state:transition:1"
        assert lock_auto_assign(1) == "lock:auto_assign:1"
        assert LOCK_TTL_STATE_TRANSITION == 10
        assert LOCK_TTL_AUTO_ASSIGN == 300


# ===== 幂等 Token 测试 =====


@pytest.mark.django_db
class TestIdempotentToken:
    """幂等 Token 测试"""

    def test_acquire_success(self):
        """首次请求获取 Token"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_get_client.return_value = mock_client

            token = IdempotentToken("req-001")
            assert token.acquire() is True

    def test_acquire_duplicate(self):
        """重复请求"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = None
            mock_get_client.return_value = mock_client

            token = IdempotentToken("req-001")
            assert token.acquire() is False

    def test_store_result(self):
        """存储处理结果"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_get_client.return_value = mock_client

            token = IdempotentToken("req-001")
            token.acquire()
            token.store_result({"success": True, "data": "result"})
            mock_client.set.assert_called()

    def test_get_stored_result(self):
        """获取已存储结果"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.return_value = json.dumps({"success": True})
            mock_get_client.return_value = mock_client

            token = IdempotentToken("req-001")
            result = token.get_stored_result()
            assert result["success"] is True

    def test_get_stored_result_none(self):
        """无已存储结果"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.return_value = None
            mock_get_client.return_value = mock_client

            token = IdempotentToken("req-001")
            assert token.get_stored_result() is None

    def test_release(self):
        """释放 Token"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_get_client.return_value = mock_client

            token = IdempotentToken("req-001")
            token.acquire()
            token.release()
            mock_client.delete.assert_called_once()

    def test_check_idempotent_helper(self):
        """check_idempotent 快捷方法"""
        with patch("apps.common.lock.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_get_client.return_value = mock_client

            assert check_idempotent("req-001") is True

    def test_idempotent_key_builder(self):
        """验证幂等 Key 构建器"""
        assert idempotent("req-001") == "idempotent:req-001"
        assert TTL_IDEMPOTENT == 5 * 60
