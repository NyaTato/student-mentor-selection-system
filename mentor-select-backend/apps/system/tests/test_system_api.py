"""
系统状态模块 API 集成测试

覆盖端点：
SystemStateViewSet（/api/v1/system/states/）：
  - list / retrieve / create（init）/ by-year / forward / rollback / histories
SystemStateScheduleViewSet（/api/v1/system/schedules/）：
  - list / retrieve / create / update / toggle-auto / update-by-year / next-transition
StateHistoryViewSet（/api/v1/system/histories/）：
  - list / retrieve

注：test_system.py 已覆盖 list 权限与 forward 基本场景，
此处补充 retrieve/create/by_year/rollback/histories 与全部调度端点。
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.enums import (
    StateTransitionType,
    SystemStateValue,
)
from apps.system.models import StateHistory, SystemState, SystemStateSchedule
from apps.system.services import SystemStateService


def _init_state(academic_year, state_value, previous=None):
    """直接通过 ORM 创建系统状态"""
    return SystemState.objects.create(
        academic_year=academic_year,
        current_state=state_value,
        previous_state=previous,
        state_changed_at=timezone.now(),
    )


# ====================================================================
# SystemStateViewSet
# ====================================================================


@pytest.mark.django_db
class TestSystemStateListRetrieveAPI:
    """系统状态 list / retrieve API 测试"""

    def test_admin_list_states(self, authenticated_client, academic_year):
        """管理员查询状态列表"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.get("/api/v1/system/states/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_retrieve_state(self, authenticated_client, academic_year):
        """查询单个系统状态"""
        state = _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.get(f"/api/v1/system/states/{state.id}/")
        assert resp.status_code == 200
        assert resp.data["data"]["current_state"] == SystemStateValue.INIT.value

    def test_retrieve_not_found(self, authenticated_client):
        """查询不存在的状态返回 404"""
        resp = authenticated_client.get("/api/v1/system/states/99999/")
        assert resp.status_code == 404

    def test_list_filter_by_academic_year(
        self, authenticated_client, academic_year
    ):
        """按学年过滤"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.get(
            f"/api/v1/system/states/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_list_unauthenticated(self, api_client):
        """未认证查询返回 401"""
        resp = api_client.get("/api/v1/system/states/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestSystemStateCreateAPI:
    """系统状态 create（init）API 测试"""

    def test_admin_init_state_success(self, authenticated_client, academic_year):
        """管理员为学年初始化系统状态"""
        resp = authenticated_client.post(
            "/api/v1/system/states/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["data"]["current_state"] == SystemStateValue.INIT.value
        assert resp.data["data"]["academic_year"] == academic_year.id

    def test_student_cannot_init_state(self, student_client, academic_year):
        """学生不能初始化系统状态（IsAdmin -> 403）"""
        resp = student_client.post(
            "/api/v1/system/states/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_cannot_init_state(self, teacher_client, academic_year):
        """导师不能初始化系统状态（IsAdmin -> 403）"""
        resp = teacher_client.post(
            "/api/v1/system/states/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_init_already_exists(self, authenticated_client, academic_year):
        """重复初始化：序列化器层 academic_year 唯一性校验返回 400

        注：Service 层 init_for_academic_year 是幂等的（返回现有状态），
        但 API 入口的 SystemStateSerializer 在 is_valid 阶段会拒绝重复的
        academic_year，故 API 层表现为 400。Service 层幂等性由
        test_system.py::test_init_already_exists 覆盖。
        """
        resp1 = authenticated_client.post(
            "/api/v1/system/states/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp1.status_code == 201
        resp2 = authenticated_client.post(
            "/api/v1/system/states/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp2.status_code == 400


@pytest.mark.django_db
class TestSystemStateForwardAPI:
    """状态推进 API 测试"""

    def test_admin_forward_success(self, authenticated_client, academic_year):
        """管理员推进状态 INIT -> FIRST_ROUND_OPEN"""
        SystemStateService().init_for_academic_year(academic_year.id)
        resp = authenticated_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 200
        assert (
            resp.data["data"]["current_state"]
            == SystemStateValue.FIRST_ROUND_OPEN.value
        )

    def test_forward_records_history(
        self, authenticated_client, academic_year
    ):
        """推进会记录历史"""
        SystemStateService().init_for_academic_year(academic_year.id)
        authenticated_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        histories = StateHistory.objects.filter(academic_year_id=academic_year.id)
        assert histories.count() == 1
        assert (
            histories.first().transition_type
            == StateTransitionType.FORWARD.value
        )

    def test_teacher_cannot_forward(self, teacher_client, academic_year):
        """导师不能推进状态（IsAdmin -> 403）"""
        SystemStateService().init_for_academic_year(academic_year.id)
        resp = teacher_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_forward_not_initialized(self, authenticated_client, academic_year):
        """未初始化的状态推进返回 404"""
        resp = authenticated_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 404

    def test_forward_terminal_state(
        self, authenticated_client, academic_year
    ):
        """FINISHED 终态不能继续推进"""
        _init_state(academic_year, SystemStateValue.FINISHED.value)
        resp = authenticated_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_forward_missing_academic_year(self, authenticated_client):
        """缺少 academic_year 字段返回 400"""
        resp = authenticated_client.post(
            "/api/v1/system/states/forward/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_forward_unauthenticated(self, api_client, academic_year):
        """未认证推进返回 401"""
        resp = api_client.post(
            "/api/v1/system/states/forward/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestSystemStateRollbackAPI:
    """状态回退 API 测试"""

    def test_admin_rollback_success(self, authenticated_client, academic_year):
        """管理员回退状态 FIRST_ROUND_OPEN -> INIT"""
        _init_state(
            academic_year,
            SystemStateValue.FIRST_ROUND_OPEN.value,
            previous=SystemStateValue.INIT.value,
        )
        resp = authenticated_client.post(
            "/api/v1/system/states/rollback/",
            {
                "academic_year": academic_year.id,
                "reason": "操作失误，需要回退重新操作",
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["current_state"] == SystemStateValue.INIT.value

    def test_rollback_records_history(
        self, authenticated_client, academic_year
    ):
        """回退会记录历史"""
        _init_state(
            academic_year,
            SystemStateValue.FIRST_ROUND_OPEN.value,
            previous=SystemStateValue.INIT.value,
        )
        authenticated_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": "管理员手动回退到前一状态"},
            format="json",
        )
        histories = StateHistory.objects.filter(academic_year_id=academic_year.id)
        assert histories.count() == 1
        assert histories.first().transition_type == StateTransitionType.ROLLBACK.value
        assert histories.first().reason == "管理员手动回退到前一状态"

    def test_student_cannot_rollback(self, student_client, academic_year):
        """学生不能回退状态（IsAdmin -> 403）"""
        _init_state(
            academic_year,
            SystemStateValue.FIRST_ROUND_OPEN.value,
            previous=SystemStateValue.INIT.value,
        )
        resp = student_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": "测试"},
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_cannot_rollback(self, teacher_client, academic_year):
        """导师不能回退状态（IsAdmin -> 403）"""
        _init_state(
            academic_year,
            SystemStateValue.FIRST_ROUND_OPEN.value,
            previous=SystemStateValue.INIT.value,
        )
        resp = teacher_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": "测试"},
            format="json",
        )
        assert resp.status_code == 403

    def test_rollback_init_forbidden(self, authenticated_client, academic_year):
        """INIT 状态不能回退（400）"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": "测试"},
            format="json",
        )
        assert resp.status_code == 400

    def test_rollback_empty_reason(self, authenticated_client, academic_year):
        """回退原因为空返回 400"""
        _init_state(
            academic_year,
            SystemStateValue.FIRST_ROUND_OPEN.value,
            previous=SystemStateValue.INIT.value,
        )
        resp = authenticated_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": ""},
            format="json",
        )
        assert resp.status_code == 400

    def test_rollback_not_initialized(self, authenticated_client, academic_year):
        """未初始化的状态回退返回 404"""
        resp = authenticated_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": "系统未初始化需要处理"},
            format="json",
        )
        assert resp.status_code == 404

    def test_rollback_unauthenticated(self, api_client, academic_year):
        """未认证回退返回 401"""
        resp = api_client.post(
            "/api/v1/system/states/rollback/",
            {"academic_year": academic_year.id, "reason": "测试"},
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestSystemStateByYearAPI:
    """按学年查询系统状态 API 测试"""

    def test_by_year_success(self, authenticated_client, academic_year):
        """按学年查询状态"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.get(
            f"/api/v1/system/states/by-year/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["academic_year"] == academic_year.id
        assert resp.data["data"]["current_state"] == SystemStateValue.INIT.value

    def test_by_year_not_found(self, authenticated_client):
        """未初始化的学年查询返回 404"""
        resp = authenticated_client.get("/api/v1/system/states/by-year/99999/")
        assert resp.status_code == 404

    def test_by_year_student_allowed(self, student_client, academic_year):
        """学生可以按学年查询状态（只读）"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = student_client.get(
            f"/api/v1/system/states/by-year/{academic_year.id}/"
        )
        assert resp.status_code == 200

    def test_by_year_unauthenticated(self, api_client, academic_year):
        """未认证查询返回 401"""
        resp = api_client.get(
            f"/api/v1/system/states/by-year/{academic_year.id}/"
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestSystemStateHistoriesAPI:
    """状态变更历史 API 测试"""

    def test_histories_success(self, authenticated_client, academic_year):
        """查询指定学年的状态变更历史"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        SystemStateService().init_for_academic_year(academic_year.id)
        SystemStateService().forward(academic_year.id)
        resp = authenticated_client.get(
            f"/api/v1/system/states/histories/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1
        assert (
            resp.data["data"][0]["to_state"]
            == SystemStateValue.FIRST_ROUND_OPEN.value
        )

    def test_histories_empty(self, authenticated_client, academic_year):
        """无历史记录返回空列表"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.get(
            f"/api/v1/system/states/histories/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"] == []

    def test_histories_student_allowed(self, student_client, academic_year):
        """学生可以查询历史（只读）"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = student_client.get(
            f"/api/v1/system/states/histories/{academic_year.id}/"
        )
        assert resp.status_code == 200

    def test_histories_unauthenticated(self, api_client, academic_year):
        """未认证查询历史返回 401"""
        resp = api_client.get(
            f"/api/v1/system/states/histories/{academic_year.id}/"
        )
        assert resp.status_code == 401


# ====================================================================
# SystemStateScheduleViewSet
# ====================================================================


@pytest.mark.django_db
class TestScheduleListRetrieveAPI:
    """调度配置 list / retrieve API 测试"""

    def test_admin_list_schedules(
        self, authenticated_client, academic_year
    ):
        """管理员查询调度配置列表"""
        SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = authenticated_client.get("/api/v1/system/schedules/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_retrieve_schedule(self, authenticated_client, academic_year):
        """查询单个调度配置"""
        schedule = SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = authenticated_client.get(
            f"/api/v1/system/schedules/{schedule.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["academic_year"] == academic_year.id

    def test_retrieve_schedule_not_found(self, authenticated_client):
        """查询不存在的调度配置返回 404"""
        resp = authenticated_client.get("/api/v1/system/schedules/99999/")
        assert resp.status_code == 404

    def test_student_can_read_schedules_but_cannot_write(
        self, student_client, academic_year
    ):
        """调度配置读契约（Task 02 有意变更）：已认证用户可读。

        前端需要用 list/retrieve 渲染时间线；写操作仍为管理员专属。
        """
        SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = student_client.get("/api/v1/system/schedules/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1
        for field in (
            "id",
            "academic_year",
            "first_round_start_at",
            "auto_enabled",
        ):
            assert field in items[0]

        resp = student_client.post(
            "/api/v1/system/schedules/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_can_read_schedules_but_cannot_write(
        self, teacher_client, academic_year
    ):
        """导师同样只能读调度配置，不能写。"""
        SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = teacher_client.get("/api/v1/system/schedules/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

        resp = teacher_client.post(
            "/api/v1/system/schedules/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_list_unauthenticated(self, api_client):
        """未认证查询调度配置返回 401"""
        resp = api_client.get("/api/v1/system/schedules/")
        assert resp.status_code == 401

    def test_list_filter_by_academic_year(
        self, authenticated_client, academic_year
    ):
        """按学年过滤调度配置"""
        SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = authenticated_client.get(
            f"/api/v1/system/schedules/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1


@pytest.mark.django_db
class TestScheduleCreateAPI:
    """调度配置 create API 测试"""

    def test_admin_create_schedule_success(
        self, authenticated_client, academic_year
    ):
        """管理员创建调度配置"""
        resp = authenticated_client.post(
            "/api/v1/system/schedules/",
            {"academic_year": academic_year.id, "auto_enabled": False},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["data"]["academic_year"] == academic_year.id

    def test_student_cannot_create_schedule(
        self, student_client, academic_year
    ):
        """学生不能创建调度配置（403）"""
        resp = student_client.post(
            "/api/v1/system/schedules/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 403

    def test_create_duplicate_schedule(
        self, authenticated_client, academic_year
    ):
        """重复创建调度配置返回 400"""
        SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = authenticated_client.post(
            "/api/v1/system/schedules/",
            {"academic_year": academic_year.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_with_schedule_times(
        self, authenticated_client, academic_year
    ):
        """创建带时间字段的调度配置"""
        start = (timezone.now() + timedelta(days=1)).isoformat()
        resp = authenticated_client.post(
            "/api/v1/system/schedules/",
            {
                "academic_year": academic_year.id,
                "first_round_start_at": start,
                "auto_enabled": True,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["data"]["auto_enabled"] is True


@pytest.mark.django_db
class TestScheduleUpdateAPI:
    """调度配置 update API 测试"""

    def test_admin_update_schedule(
        self, authenticated_client, academic_year
    ):
        """管理员更新调度配置（PATCH）"""
        schedule = SystemStateSchedule.objects.create(
            academic_year=academic_year, auto_enabled=False
        )
        resp = authenticated_client.patch(
            f"/api/v1/system/schedules/{schedule.id}/",
            {"auto_enabled": True},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["auto_enabled"] is True

    def test_student_cannot_update_schedule(
        self, student_client, academic_year
    ):
        """学生不能更新调度配置（403）"""
        schedule = SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = student_client.patch(
            f"/api/v1/system/schedules/{schedule.id}/",
            {"auto_enabled": True},
            format="json",
        )
        assert resp.status_code == 403

    def test_update_not_found(self, authenticated_client):
        """更新不存在的调度配置返回 404"""
        resp = authenticated_client.patch(
            "/api/v1/system/schedules/99999/",
            {"auto_enabled": True},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestScheduleToggleAutoAPI:
    """调度配置 toggle-auto API 测试"""

    def test_toggle_auto_enable(self, authenticated_client, academic_year):
        """启用自动切换"""
        SystemStateSchedule.objects.create(
            academic_year=academic_year, auto_enabled=False
        )
        resp = authenticated_client.post(
            "/api/v1/system/schedules/toggle-auto/",
            {"academic_year": academic_year.id, "enabled": True},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["auto_enabled"] is True

    def test_toggle_auto_disable(self, authenticated_client, academic_year):
        """禁用自动切换"""
        SystemStateSchedule.objects.create(
            academic_year=academic_year, auto_enabled=True
        )
        resp = authenticated_client.post(
            "/api/v1/system/schedules/toggle-auto/",
            {"academic_year": academic_year.id, "enabled": False},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["auto_enabled"] is False

    def test_toggle_auto_missing_params(self, authenticated_client):
        """缺少参数返回 400"""
        resp = authenticated_client.post(
            "/api/v1/system/schedules/toggle-auto/",
            {"academic_year": 1},
            format="json",
        )
        assert resp.status_code == 400

    def test_toggle_auto_student_forbidden(self, student_client, academic_year):
        """学生不能启停自动切换（403）"""
        SystemStateSchedule.objects.create(academic_year=academic_year)
        resp = student_client.post(
            "/api/v1/system/schedules/toggle-auto/",
            {"academic_year": academic_year.id, "enabled": True},
            format="json",
        )
        assert resp.status_code == 403

    def test_toggle_auto_not_found(self, authenticated_client):
        """未配置的学年启停返回 404"""
        resp = authenticated_client.post(
            "/api/v1/system/schedules/toggle-auto/",
            {"academic_year": 99999, "enabled": True},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestScheduleUpdateByYearAPI:
    """调度配置 update-by-year API 测试"""

    def test_update_by_year_success(self, authenticated_client, academic_year):
        """按学年更新调度配置"""
        SystemStateSchedule.objects.create(
            academic_year=academic_year, auto_enabled=False
        )
        new_time = (timezone.now() + timedelta(days=2)).isoformat()
        resp = authenticated_client.put(
            "/api/v1/system/schedules/update-by-year/",
            {
                "academic_year": academic_year.id,
                "first_round_start_at": new_time,
                "auto_enabled": True,
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["auto_enabled"] is True

    def test_update_by_year_missing_academic_year(
        self, authenticated_client
    ):
        """缺少 academic_year 返回 400"""
        resp = authenticated_client.put(
            "/api/v1/system/schedules/update-by-year/",
            {"auto_enabled": True},
            format="json",
        )
        assert resp.status_code == 400

    def test_update_by_year_student_forbidden(
        self, student_client, academic_year
    ):
        """学生不能按学年更新调度配置（403）"""
        resp = student_client.put(
            "/api/v1/system/schedules/update-by-year/",
            {"academic_year": academic_year.id, "auto_enabled": True},
            format="json",
        )
        assert resp.status_code == 403

    def test_update_by_year_not_found(self, authenticated_client):
        """未配置的学年更新返回 404"""
        resp = authenticated_client.put(
            "/api/v1/system/schedules/update-by-year/",
            {"academic_year": 99999, "auto_enabled": True},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestScheduleNextTransitionAPI:
    """调度配置 next-transition API 测试"""

    def test_next_transition_success(
        self, authenticated_client, academic_year
    ):
        """查询下一次自动切换信息"""
        scheduled = timezone.now() + timedelta(hours=1)
        _init_state(academic_year, SystemStateValue.INIT.value)
        SystemStateSchedule.objects.create(
            academic_year=academic_year,
            first_round_start_at=scheduled,
            auto_enabled=True,
        )
        resp = authenticated_client.get(
            f"/api/v1/system/schedules/next-transition/{academic_year.id}/"
        )
        assert resp.status_code == 200
        data = resp.data["data"]
        assert data is not None
        assert data["current_state"] == SystemStateValue.INIT.value
        assert data["next_state"] == SystemStateValue.FIRST_ROUND_OPEN.value

    def test_next_transition_no_schedule(
        self, authenticated_client, academic_year
    ):
        """无调度配置返回 null data"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = authenticated_client.get(
            f"/api/v1/system/schedules/next-transition/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"] is None

    def test_next_transition_finished(
        self, authenticated_client, academic_year
    ):
        """FINISHED 状态无下次切换"""
        _init_state(academic_year, SystemStateValue.FINISHED.value)
        SystemStateSchedule.objects.create(
            academic_year=academic_year, auto_enabled=True
        )
        resp = authenticated_client.get(
            f"/api/v1/system/schedules/next-transition/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"] is None

    def test_next_transition_student_can_read(
        self, student_client, academic_year
    ):
        """读契约：已认证用户可查询下次切换信息（不再 403）。"""
        SystemStateSchedule.objects.create(
            academic_year=academic_year, auto_enabled=True
        )
        resp = student_client.get(
            f"/api/v1/system/schedules/next-transition/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert "data" in resp.data


# ====================================================================
# StateHistoryViewSet
# ====================================================================


@pytest.mark.django_db
class TestStateHistoryListRetrieveAPI:
    """状态变更历史 list / retrieve API 测试"""

    def test_admin_list_histories(
        self, authenticated_client, academic_year
    ):
        """管理员查询历史列表"""
        StateHistory.objects.create(
            academic_year=academic_year,
            from_state=SystemStateValue.INIT.value,
            to_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            transition_type=StateTransitionType.FORWARD.value,
        )
        resp = authenticated_client.get("/api/v1/system/histories/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_retrieve_history(
        self, authenticated_client, academic_year
    ):
        """查询单条历史"""
        history = StateHistory.objects.create(
            academic_year=academic_year,
            from_state=SystemStateValue.INIT.value,
            to_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            transition_type=StateTransitionType.FORWARD.value,
        )
        resp = authenticated_client.get(
            f"/api/v1/system/histories/{history.id}/"
        )
        assert resp.status_code == 200
        assert (
            resp.data["data"]["to_state"]
            == SystemStateValue.FIRST_ROUND_OPEN.value
        )

    def test_retrieve_history_not_found(self, authenticated_client):
        """查询不存在的历史返回 404"""
        resp = authenticated_client.get("/api/v1/system/histories/99999/")
        assert resp.status_code == 404

    def test_list_histories_filter_by_academic_year(
        self, authenticated_client, academic_year
    ):
        """按学年过滤历史"""
        StateHistory.objects.create(
            academic_year=academic_year,
            from_state=SystemStateValue.INIT.value,
            to_state=SystemStateValue.FIRST_ROUND_OPEN.value,
            transition_type=StateTransitionType.FORWARD.value,
        )
        resp = authenticated_client.get(
            f"/api/v1/system/histories/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_student_can_list_histories(self, student_client, academic_year):
        """学生可以查看历史列表（只读）"""
        resp = student_client.get("/api/v1/system/histories/")
        assert resp.status_code == 200

    def test_teacher_can_list_histories(self, teacher_client):
        """导师可以查看历史列表（只读）"""
        resp = teacher_client.get("/api/v1/system/histories/")
        assert resp.status_code == 200

    def test_list_histories_unauthenticated(self, api_client):
        """未认证查询历史返回 401"""
        resp = api_client.get("/api/v1/system/histories/")
        assert resp.status_code == 401
