"""
系统状态模块测试
覆盖 Model / Serializer / Service / Permission
"""
import pytest

from apps.common.enums import (
    StateTransitionType,
    SystemStateValue,
    UserRole,
)
from apps.common.exceptions import (
    BusinessException,
    NotFoundError,
    StateTransitionError,
)
from apps.system.models import StateHistory, SystemState, SystemStateSchedule
from apps.system.services import (
    SystemStateScheduleService,
    SystemStateService,
)


@pytest.mark.django_db
class TestSystemStateModel:
    """SystemState Model 测试"""

    def test_create_system_state(self, academic_year):
        from django.utils import timezone

        state = SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        assert state.id is not None
        assert state.current_state == SystemStateValue.INIT.value
        assert state.previous_state is None

    def test_one_per_academic_year(self, academic_year):
        from django.utils import timezone

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        with pytest.raises(Exception):  # IntegrityError
            SystemState.objects.create(
                academic_year=academic_year,
                current_state=SystemStateValue.FIRST_ROUND_OPEN.value,
                state_changed_at=timezone.now(),
            )


@pytest.mark.django_db
class TestStateHistoryModel:
    """StateHistory Model 测试"""

    def test_create_state_history(self, academic_year):
        history = StateHistory.objects.create(
            academic_year=academic_year,
            from_state=SystemStateValue.INIT.value,
            to_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            transition_type=StateTransitionType.FORWARD.value,
        )
        assert history.id is not None
        assert history.from_state == SystemStateValue.INIT.value
        assert history.to_state == SystemStateValue.FIRST_ROUND_OPEN.value


@pytest.mark.django_db
class TestSystemStateService:
    """SystemStateService 测试"""

    def test_init_for_academic_year(self, academic_year):
        service = SystemStateService()
        state = service.init_for_academic_year(academic_year.id)
        assert state.current_state == SystemStateValue.INIT.value
        assert state.previous_state is None

    def test_init_already_exists(self, academic_year):
        """重复初始化返回现有状态"""
        service = SystemStateService()
        state1 = service.init_for_academic_year(academic_year.id)
        state2 = service.init_for_academic_year(academic_year.id)
        assert state1.id == state2.id

    def test_get_by_academic_year(self, academic_year):
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)
        state = service.get_by_academic_year(academic_year.id)
        assert state.academic_year_id == academic_year.id

    def test_get_by_academic_year_not_found(self):
        service = SystemStateService()
        with pytest.raises(NotFoundError):
            service.get_by_academic_year(99999)

    def test_forward(self, academic_year):
        """测试状态推进 INIT -> FIRST_ROUND_OPEN"""
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)

        state = service.forward(academic_year.id)
        assert state.current_state == SystemStateValue.FIRST_ROUND_OPEN.value
        assert state.previous_state == SystemStateValue.INIT.value

    def test_forward_multiple_steps(self, academic_year):
        """测试连续推进"""
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)

        # INIT -> FIRST_ROUND_OPEN
        service.forward(academic_year.id)
        # FIRST_ROUND_OPEN -> TEACHER_REVIEW
        state = service.forward(academic_year.id)
        assert state.current_state == SystemStateValue.TEACHER_REVIEW.value

    def test_forward_finished_terminal(self, academic_year):
        """FINISHED 是终态，不能继续推进"""
        from django.utils import timezone

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FINISHED.value,
            state_changed_at=timezone.now(),
        )
        service = SystemStateService()
        with pytest.raises(StateTransitionError):
            service.forward(academic_year.id)

    def test_forward_not_initialized(self, academic_year):
        """未初始化的系统状态不能推进"""
        service = SystemStateService()
        with pytest.raises(NotFoundError):
            service.forward(academic_year.id)

    def test_forward_records_history(self, academic_year):
        """推进会记录历史"""
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)
        service.forward(academic_year.id)

        histories = StateHistory.objects.filter(academic_year_id=academic_year.id)
        assert histories.count() == 1
        history = histories.first()
        assert history.from_state == SystemStateValue.INIT.value
        assert history.to_state == SystemStateValue.FIRST_ROUND_OPEN.value
        assert history.transition_type == StateTransitionType.FORWARD.value

    def test_rollback(self, academic_year):
        """测试状态回退 FIRST_ROUND_OPEN -> INIT"""
        from django.utils import timezone

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            previous_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        service = SystemStateService()
        state = service.rollback(academic_year.id, reason="管理员手动回退到前一状态")
        assert state.current_state == SystemStateValue.INIT.value

    def test_rollback_init_forbidden(self, academic_year):
        """INIT 不能回退"""
        from django.utils import timezone

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        service = SystemStateService()
        with pytest.raises(StateTransitionError):
            service.rollback(academic_year.id, reason="管理员手动回退到前一状态")

    def test_rollback_empty_reason(self, academic_year):
        """回退原因不能为空"""
        from django.utils import timezone

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            previous_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        service = SystemStateService()
        with pytest.raises(BusinessException):
            service.rollback(academic_year.id, reason="")

    def test_rollback_records_history(self, academic_year):
        """回退会记录历史"""
        from django.utils import timezone

        SystemState.objects.create(
            academic_year=academic_year,
            current_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            previous_state=SystemStateValue.INIT.value,
            state_changed_at=timezone.now(),
        )
        service = SystemStateService()
        service.rollback(academic_year.id, reason="管理员手动回退到前一状态")

        histories = StateHistory.objects.filter(academic_year_id=academic_year.id)
        assert histories.count() == 1
        history = histories.first()
        assert history.transition_type == StateTransitionType.ROLLBACK.value
        assert history.reason == "管理员手动回退到前一状态"

    def test_get_current_state_value(self, academic_year):
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)
        value = service.get_current_state_value(academic_year.id)
        assert value == SystemStateValue.INIT.value

    def test_is_state(self, academic_year):
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)
        assert service.is_state(
            academic_year.id, SystemStateValue.INIT.value
        )
        assert not service.is_state(
            academic_year.id, SystemStateValue.FINISHED.value
        )

    def test_is_state_not_initialized(self):
        """未初始化返回 False"""
        service = SystemStateService()
        assert not service.is_state(99999, SystemStateValue.INIT.value)

    def test_full_lifecycle(self, academic_year):
        """测试完整状态机生命周期"""
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)

        # INIT -> FIRST_ROUND_OPEN -> TEACHER_REVIEW -> SECOND_ROUND_OPEN -> AUTO_ASSIGN -> FINISHED
        service.forward(academic_year.id)
        service.forward(academic_year.id)
        service.forward(academic_year.id)
        service.forward(academic_year.id)
        state = service.forward(academic_year.id)
        assert state.current_state == SystemStateValue.FINISHED.value

        # 历史记录
        histories = StateHistory.objects.filter(academic_year_id=academic_year.id)
        assert histories.count() == 5


@pytest.mark.django_db
class TestSystemStateScheduleService:
    """SystemStateScheduleService 测试"""

    def test_create_schedule(self, academic_year):
        service = SystemStateScheduleService()
        schedule = service.create({"academic_year": academic_year})
        assert schedule.id is not None
        assert schedule.academic_year_id == academic_year.id

    def test_create_duplicate_schedule(self, academic_year):
        SystemStateSchedule.objects.create(academic_year=academic_year)
        service = SystemStateScheduleService()
        with pytest.raises(BusinessException):
            service.create({"academic_year": academic_year})

    def test_toggle_auto(self, academic_year):
        SystemStateSchedule.objects.create(academic_year=academic_year)
        service = SystemStateScheduleService()
        schedule = service.toggle_auto(academic_year.id, True)
        assert schedule.auto_enabled is True

        schedule = service.toggle_auto(academic_year.id, False)
        assert schedule.auto_enabled is False


@pytest.mark.django_db
class TestSystemStatePermission:
    """系统状态权限测试"""

    def test_admin_can_list_states(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/system/states/")
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list_states(self, api_client):
        resp = api_client.get("/api/v1/system/states/")
        assert resp.status_code == 401

    def test_student_can_list_states(self, student_client):
        """学生可以查看状态"""
        resp = student_client.get("/api/v1/system/states/")
        assert resp.status_code == 200

    def test_student_cannot_forward(self, student_client, academic_year):
        """学生不能推进状态"""
        resp = student_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_admin_can_forward(self, authenticated_client, academic_year):
        """管理员可以推进状态"""
        # 先初始化
        service = SystemStateService()
        service.init_for_academic_year(academic_year.id)

        resp = authenticated_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 200
