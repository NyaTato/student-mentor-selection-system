"""Celery 任务测试

测试覆盖：
- system.tasks: check_and_progress_state / auto_close_academic_year / run_auto_assignment
- imports.tasks: process_excel_import
- assignments.tasks: run_auto_assignment / revoke_auto_assignment

使用 Celery eager 模式（@task_always_eager=True）同步执行任务。
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.common.enums import (
    AcademicYearStatus,
    StateTransitionType,
    SystemStateValue,
    UserRole,
    UserStatus,
)
from apps.academic_year.models import AcademicYear
from apps.system.models import SystemState, SystemStateSchedule


# ===== system.tasks 测试 =====


@pytest.mark.django_db
class TestCheckAndProgressState:
    """自动状态推进任务测试"""

    def test_no_schedules(self, celery_eager):
        """无调度配置时返回空列表"""
        from apps.system.tasks import check_and_progress_state
        result = check_and_progress_state()
        assert result == []

    def test_auto_disabled_skipped(self, celery_eager, academic_year):
        """auto_enabled=False 不推进"""
        from apps.system.tasks import check_and_progress_state

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(hours=1),
        )
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=timezone.now() - timedelta(minutes=30),
            auto_enabled=False,
        )

        result = check_and_progress_state()
        assert result == []

    def test_finished_state_skipped(self, celery_eager, academic_year):
        """FINISHED 状态不推进"""
        from apps.system.tasks import check_and_progress_state

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FINISHED.value,
            state_changed_at=timezone.now() - timedelta(hours=1),
        )
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            auto_enabled=True,
        )

        result = check_and_progress_state()
        assert result == []

    def test_not_reached_scheduled_time(self, celery_eager, academic_year):
        """未到调度时间不推进"""
        from apps.system.tasks import check_and_progress_state

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(hours=1),
        )
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=timezone.now() + timedelta(hours=1),  # 未来时间
            auto_enabled=True,
        )

        result = check_and_progress_state()
        assert result == []

    def test_manual_operation_priority(self, celery_eager, academic_year):
        """手动操作优先（state_changed_at >= scheduled_at）"""
        from apps.system.tasks import check_and_progress_state

        scheduled_at = timezone.now() - timedelta(minutes=30)
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FIRST_ROUND_OPEN.value,  # 已手动推进
            state_changed_at=timezone.now() - timedelta(minutes=10),  # 手动操作时间 < scheduled_at
        )
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=scheduled_at,
            auto_enabled=True,
        )

        # state_changed_at (now-10min) >= scheduled_at (now-30min) → 已手动推进，跳过
        result = check_and_progress_state()
        # 由于 state_changed_at >= scheduled_at，不会推进
        assert academic_year.id not in result

    def test_auto_progress_success(self, celery_eager, academic_year):
        """自动推进成功"""
        from apps.system.tasks import check_and_progress_state

        # 创建系统状态（INIT）
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(hours=2),
        )
        # 创建调度配置（first_round_start_at 已过）
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=timezone.now() - timedelta(hours=1),
            auto_enabled=True,
        )

        # Mock 分布式锁，避免依赖真实 Redis
        with patch("apps.system.tasks.DistributedLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_lock_class.return_value = mock_lock

            result = check_and_progress_state()
            assert academic_year.id in result

        # 验证状态已推进
        state = SystemState.objects.get(academic_year=academic_year)
        assert state.current_state == SystemStateValue.FIRST_ROUND_OPEN.value


@pytest.mark.django_db
class TestAutoCloseAcademicYear:
    """自动关闭学年任务测试"""

    def test_close_success(self, celery_eager, academic_year):
        """成功关闭学年"""
        from apps.system.tasks import auto_close_academic_year

        result = auto_close_academic_year(academic_year.id)
        assert result["status"] == "archived"

        academic_year.refresh_from_db()
        assert academic_year.status == AcademicYearStatus.ARCHIVED.value

    def test_already_closed(self, celery_eager, academic_year):
        """学年已关闭"""
        from apps.system.tasks import auto_close_academic_year

        academic_year.status = AcademicYearStatus.ARCHIVED.value
        academic_year.save()

        result = auto_close_academic_year(academic_year.id)
        assert result["status"] == "already_archived"

    def test_year_not_found(self, celery_eager):
        """学年不存在"""
        from apps.system.tasks import auto_close_academic_year

        result = auto_close_academic_year(99999)
        assert result["status"] == "not_found"


@pytest.mark.django_db
class TestRunAutoAssignmentTask:
    """自动分配任务测试"""

    def test_run_auto_assignment(self, celery_eager):
        """触发自动分配任务（mock AutoAssignmentService）"""
        from apps.system.tasks import run_auto_assignment
        from apps.assignments.services import AutoAssignmentResult

        mock_result = AutoAssignmentResult(
            log_id=1,
            total_unassigned=3,
            assigned_count=3,
            failed_count=0,
            is_all_assigned=True,
        )
        with patch(
            "apps.assignments.services.AutoAssignmentService.run",
            return_value=mock_result,
        ):
            result = run_auto_assignment(academic_year_id=1, triggered_by=1)
        assert result["status"] == "completed"
        assert result["academic_year_id"] == 1
        assert result["assigned_count"] == 3
        assert result["is_all_assigned"] is True


# ===== imports.tasks 测试 =====


@pytest.mark.django_db
class TestProcessExcelImport:
    """Excel 导入任务测试"""

    def test_task_not_found(self, celery_eager):
        """任务不存在"""
        from apps.imports.tasks import process_excel_import

        result = process_excel_import(99999)
        assert result["status"] == "not_found"

    def test_already_completed(self, celery_eager, academic_year, admin_user):
        """任务已完成"""
        from apps.imports.tasks import process_excel_import
        from apps.common.enums import ImportTaskStatus
        from apps.imports.models import ImportTask

        task = ImportTask.objects.create(
            academic_year=academic_year,
            role=UserRole.STUDENT.value,
            status=ImportTaskStatus.SUCCESS.value,
            file_name="test.xlsx",
            file_size=1024,
            total_rows=10,
            success_count=10,
            failed_count=0,
            triggered_by=admin_user,
        )

        result = process_excel_import(task.id)
        assert result["status"] == "already_completed"


# ===== assignments.tasks 测试 =====


@pytest.mark.django_db
class TestAssignmentsTasks:
    """分配模块任务测试"""

    def test_run_auto_assignment(self, celery_eager):
        """执行自动分配任务（mock AutoAssignmentService）"""
        from apps.assignments.tasks import run_auto_assignment
        from apps.assignments.services import AutoAssignmentResult

        mock_result = AutoAssignmentResult(
            log_id=1,
            total_unassigned=3,
            assigned_count=3,
            failed_count=0,
            is_all_assigned=True,
        )
        with patch(
            "apps.assignments.services.AutoAssignmentService.run",
            return_value=mock_result,
        ):
            result = run_auto_assignment(academic_year_id=1, triggered_by=1)
        assert result["status"] == "completed"
        assert result["assigned_count"] == 3
        assert result["is_all_assigned"] is True

    def test_revoke_auto_assignment(self, celery_eager):
        """撤销自动分配任务（mock AutoAssignmentService）"""
        from apps.assignments.tasks import revoke_auto_assignment

        mock_result = {"revoked_count": 2}
        with patch(
            "apps.assignments.services.AutoAssignmentService.revoke",
            return_value=mock_result,
        ):
            result = revoke_auto_assignment(
                academic_year_id=1,
                auto_assignment_log_id=5,
                revoked_by=1,
            )
        assert result["status"] == "completed"
        assert result["revoked_count"] == 2
