"""自动时间切换测试

依据 DATABASE.md 7.10 自动时间切换：
- 每分钟扫描 system_state_schedule
- 手动优先（state_changed_at vs scheduled_at）
- 分布式锁防并发
- 回退兼容

测试覆盖：
- SystemStateService.auto_forward: 自动推进 + AUTO transition type
- SystemStateScheduleService: update_schedule / toggle_auto / get_next_transition
- 回退兼容场景
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.common.enums import (
    StateTransitionType,
    SystemStateValue,
)
from apps.system.models import StateHistory, SystemState, SystemStateSchedule
from apps.system.services import (
    SystemStateService,
    SystemStateScheduleService,
)


@pytest.mark.django_db
class TestAutoForward:
    """自动推进测试"""

    def test_auto_forward_from_init(self, academic_year):
        """从 INIT 自动推进到 FIRST_ROUND_OPEN"""
        service = SystemStateService()

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(hours=1),
        )

        state = service.auto_forward(academic_year.id)

        assert state.current_state == SystemStateValue.FIRST_ROUND_OPEN.value
        assert state.previous_state == SystemStateValue.INIT.value

        # 验证历史记录使用 AUTO transition type
        history = StateHistory.objects.get(academic_year=academic_year)
        assert history.transition_type == StateTransitionType.AUTO.value
        assert history.operator is None
        assert history.from_state == SystemStateValue.INIT.value
        assert history.to_state == SystemStateValue.FIRST_ROUND_OPEN.value

    def test_auto_forward_from_first_round(self, academic_year):
        """从 FIRST_ROUND_OPEN 自动推进到 TEACHER_REVIEW"""
        service = SystemStateService()

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            previous_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(hours=1),
        )

        state = service.auto_forward(academic_year.id)

        assert state.current_state == SystemStateValue.TEACHER_REVIEW.value

        history = StateHistory.objects.get(academic_year=academic_year)
        assert history.transition_type == StateTransitionType.AUTO.value

    def test_auto_forward_finished_state_raises(self, academic_year):
        """FINISHED 状态不能自动推进"""
        from apps.common.exceptions import StateTransitionError

        service = SystemStateService()

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FINISHED.value,
            previous_state=SystemStateValue.AUTO_ASSIGN.value,
            state_changed_at=timezone.now() - timedelta(hours=1),
        )

        with pytest.raises(StateTransitionError):
            service.auto_forward(academic_year.id)

    def test_auto_forward_updates_state_changed_at(self, academic_year):
        """自动推进更新 state_changed_at"""
        service = SystemStateService()

        old_time = timezone.now() - timedelta(hours=2)
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=old_time,
        )

        state = service.auto_forward(academic_year.id)

        assert state.state_changed_at > old_time


@pytest.mark.django_db
class TestScheduleService:
    """调度配置服务测试"""

    def test_create_schedule(self, academic_year):
        """创建调度配置"""
        service = SystemStateScheduleService()

        schedule = service.create({
            "academic_year": academic_year,
            "first_round_start_at": timezone.now() + timedelta(days=1),
            "auto_enabled": False,
        })

        assert schedule.academic_year_id == academic_year.id
        assert schedule.auto_enabled is False

    def test_create_duplicate_raises(self, academic_year):
        """重复创建抛异常"""
        from apps.common.exceptions import BusinessException

        service = SystemStateScheduleService()

        service.create({
            "academic_year": academic_year,
            "auto_enabled": False,
        })

        with pytest.raises(BusinessException):
            service.create({
                "academic_year": academic_year,
                "auto_enabled": True,
            })

    def test_update_schedule(self, academic_year):
        """更新调度配置"""
        service = SystemStateScheduleService()

        schedule = service.create({
            "academic_year": academic_year,
            "auto_enabled": False,
        })

        new_time = timezone.now() + timedelta(days=2)
        updated = service.update_schedule(academic_year.id, {
            "first_round_start_at": new_time,
            "auto_enabled": True,
        })

        assert updated.first_round_start_at == new_time
        assert updated.auto_enabled is True

    def test_toggle_auto(self, academic_year):
        """启停自动切换"""
        service = SystemStateScheduleService()

        service.create({
            "academic_year": academic_year,
            "auto_enabled": False,
        })

        schedule = service.toggle_auto(academic_year.id, True)
        assert schedule.auto_enabled is True

        schedule = service.toggle_auto(academic_year.id, False)
        assert schedule.auto_enabled is False

    def test_get_by_academic_year_not_found(self):
        """学年未配置调度"""
        from apps.common.exceptions import NotFoundError

        service = SystemStateScheduleService()
        with pytest.raises(NotFoundError):
            service.get_by_academic_year(99999)

    def test_get_next_transition(self, academic_year):
        """获取下一次自动切换信息"""
        service = SystemStateScheduleService()

        scheduled_time = timezone.now() + timedelta(hours=1)
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        service.create({
            "academic_year": academic_year,
            "first_round_start_at": scheduled_time,
            "auto_enabled": True,
        })

        next_info = service.get_next_transition(academic_year.id)
        assert next_info is not None
        assert next_info["current_state"] == SystemStateValue.INIT.value
        assert next_info["next_state"] == SystemStateValue.FIRST_ROUND_OPEN.value
        assert next_info["scheduled_at"] == scheduled_time
        assert next_info["time_field"] == "first_round_start_at"

    def test_get_next_transition_finished(self, academic_year):
        """FINISHED 状态无下次切换"""
        service = SystemStateScheduleService()

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FINISHED.value,
            state_changed_at=timezone.now(),
        )
        service.create({
            "academic_year": academic_year,
            "auto_enabled": True,
        })

        next_info = service.get_next_transition(academic_year.id)
        assert next_info is None

    def test_get_next_transition_no_schedule(self, academic_year):
        """无调度配置返回 None"""
        service = SystemStateScheduleService()

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )

        next_info = service.get_next_transition(academic_year.id)
        assert next_info is None


@pytest.mark.django_db
class TestRollbackCompatibility:
    """回退兼容测试

    依据 DATABASE.md 7.10：
    - 手动优先：state_changed_at >= scheduled_at 时跳过自动切换
    - 回退后 state_changed_at 更新为当前时间，自动切换不会覆盖
    """

    def test_manual_rollback_prevents_auto_transition(self, academic_year, celery_eager):
        """手动回退后自动切换不覆盖"""
        from apps.system.tasks import check_and_progress_state

        # 当前状态 FIRST_ROUND_OPEN
        scheduled_at = timezone.now() - timedelta(hours=1)
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            previous_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(minutes=5),  # 手动回退后时间 < scheduled_at
        )
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=scheduled_at,
            first_round_end_at=timezone.now() - timedelta(minutes=30),
            auto_enabled=True,
        )

        # Mock 分布式锁
        with patch("apps.system.tasks.DistributedLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_lock_class.return_value = mock_lock

            result = check_and_progress_state()

        # 由于 state_changed_at (now-5min) >= scheduled_at (now-30min for first_round_end_at)，
        # 实际上 first_round_end_at 是 now-30min, state_changed_at 是 now-5min
        # state_changed_at (now-5min) >= scheduled_at (now-30min) → 手动操作优先，跳过
        # 等等，让我重新检查...

        # state = FIRST_ROUND_OPEN
        # time_field = first_round_end_at (now-30min)
        # scheduled_at = now-30min
        # state_changed_at = now-5min
        # state_changed_at (now-5min) >= scheduled_at (now-30min) → True, 跳过
        assert academic_year.id not in result

    def test_auto_transition_after_rollback_with_new_schedule(self, academic_year, celery_eager):
        """回退后配置新的调度时间，自动切换可正常执行"""
        from apps.system.tasks import check_and_progress_state

        # 回退到 INIT，state_changed_at 为当前时间
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now() - timedelta(hours=2),
        )
        # 新的 first_round_start_at 已过
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=timezone.now() - timedelta(hours=1),
            auto_enabled=True,
        )

        with patch("apps.system.tasks.DistributedLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_lock_class.return_value = mock_lock

            result = check_and_progress_state()

        assert academic_year.id in result

        state = SystemState.objects.get(academic_year=academic_year)
        assert state.current_state == SystemStateValue.FIRST_ROUND_OPEN.value
