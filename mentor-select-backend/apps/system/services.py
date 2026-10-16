"""
系统状态业务服务

实现状态机的推进与回退，记录状态变更历史。

状态机定义（依据 PROJECT.md / DATABASE.md）：
    INIT(0) -> FIRST_ROUND_OPEN(1) -> TEACHER_REVIEW(2)
            -> SECOND_ROUND_OPEN(3) -> AUTO_ASSIGN(4) -> FINISHED(5)

推进规则：
- 只能按状态机正向推进，一次一步
- 不允许跳过中间状态

回退规则：
- 只能回退一步（previous_state -> current_state 的反向）
- INIT 状态不能回退
- 回退需记录原因

暂不实现：自动时间调度（SystemStateSchedule.auto_enabled）
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.common.enums import (
    StateTransitionType,
    SystemStateValue,
)
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import (
    BusinessException,
    NotFoundError,
    StateTransitionError,
)
from apps.common.logger import get_logger, log_state_transition
from apps.common.services import BaseService
from apps.monitoring.services import MetricsService
from apps.system.models import SystemState, SystemStateSchedule
from apps.system.repositories import (
    StateHistoryRepository,
    SystemStateRepository,
    SystemStateScheduleRepository,
)

logger = get_logger("system.services")


# 状态机推进规则：current_state -> next_state
FORWARD_TRANSITIONS = {
    SystemStateValue.INIT.value: SystemStateValue.FIRST_ROUND_OPEN.value,
    SystemStateValue.FIRST_ROUND_OPEN.value: SystemStateValue.TEACHER_REVIEW.value,
    SystemStateValue.TEACHER_REVIEW.value: SystemStateValue.SECOND_ROUND_OPEN.value,
    SystemStateValue.SECOND_ROUND_OPEN.value: SystemStateValue.AUTO_ASSIGN.value,
    SystemStateValue.AUTO_ASSIGN.value: SystemStateValue.FINISHED.value,
    SystemStateValue.FINISHED.value: None,  # 终态，不能推进
}

# 状态机回退规则：current_state -> previous_state
BACKWARD_TRANSITIONS = {
    SystemStateValue.FIRST_ROUND_OPEN.value: SystemStateValue.INIT.value,
    SystemStateValue.TEACHER_REVIEW.value: SystemStateValue.FIRST_ROUND_OPEN.value,
    SystemStateValue.SECOND_ROUND_OPEN.value: SystemStateValue.TEACHER_REVIEW.value,
    SystemStateValue.AUTO_ASSIGN.value: SystemStateValue.SECOND_ROUND_OPEN.value,
    SystemStateValue.FINISHED.value: SystemStateValue.AUTO_ASSIGN.value,
    SystemStateValue.INIT.value: None,  # 初始态，不能回退
}


class SystemStateService(BaseService):
    """系统状态业务服务"""

    repository = SystemStateRepository()
    history_repository = StateHistoryRepository()

    # ===== 查询 =====

    def list(self, filters: dict | None = None, order_by: list | None = None):
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> SystemState:
        return self.repository.get_by_id(pk)

    def get_by_academic_year(self, academic_year_id: int) -> SystemState:
        """按学年查询系统状态"""
        state = self.repository.get_by_academic_year(academic_year_id)
        if state is None:
            raise NotFoundError(
                f"学年 {academic_year_id} 未初始化系统状态",
            )
        return state

    def list_histories(self, academic_year_id: int):
        """查询学年的状态变更历史"""
        return self.history_repository.list_by_academic_year(academic_year_id)

    # ===== 初始化 =====

    @transaction.atomic
    def init_for_academic_year(self, academic_year_id: int) -> SystemState:
        """为学年初始化系统状态

        - 若已存在则返回当前状态
        - 否则创建初始状态（INIT）
        """
        existing = self.repository.get_by_academic_year(academic_year_id)
        if existing:
            return existing

        state = self.repository.create(
            academic_year_id=academic_year_id,
            current_state=SystemStateValue.INIT.value,
            previous_state=None,
            state_changed_at=timezone.now(),
        )
        logger.info("SystemState initialized: year=%s", academic_year_id)
        return state

    # ===== 状态推进 =====

    @transaction.atomic
    def forward(
        self, academic_year_id: int, operator_user=None
    ) -> SystemState:
        """状态推进（正向一步）

        业务规则：
        - 必须按状态机顺序推进
        - FINISHED 是终态，不能继续推进
        - 记录 StateHistory
        """
        state = self.get_by_academic_year(academic_year_id)
        current = state.current_state
        next_state = FORWARD_TRANSITIONS.get(current)

        if next_state is None:
            raise StateTransitionError(
                f"当前状态 {state.get_current_state_display()} 不能继续推进",
            )

        # 更新状态（通过 Repository，含乐观锁版本递增）
        state = self.repository.update(
            state,
            {
                "previous_state": current,
                "current_state": next_state,
                "state_changed_at": timezone.now(),
            },
        )

        # 记录历史（通过 Repository）
        self.history_repository.create(
            academic_year_id=academic_year_id,
            from_state=current,
            to_state=next_state,
            transition_type=StateTransitionType.FORWARD.value,
            operator=operator_user,
        )

        log_state_transition(
            user_id=operator_user.id if operator_user else None,
            academic_year_id=academic_year_id,
            from_state=current,
            to_state=next_state,
            transition_type="FORWARD",
        )
        logger.info(
            "State forward: year=%s, %s -> %s, operator=%s",
            academic_year_id, current, next_state,
            operator_user.id if operator_user else None,
        )
        MetricsService.record_state_transition(current, next_state)
        return state

    # ===== 状态回退 =====

    @transaction.atomic
    def rollback(
        self,
        academic_year_id: int,
        reason: str,
        operator_user=None,
    ) -> SystemState:
        """状态回退（反向一步）

        业务规则：
        - 只能回退一步
        - INIT 不能回退
        - 必须记录回退原因
        - 记录 StateHistory
        """
        if not reason or not reason.strip():
            raise BusinessException("回退原因不能为空")
        if len(reason.strip()) < 10:
            raise BusinessException("回退原因不能少于 10 个字符")

        state = self.get_by_academic_year(academic_year_id)
        current = state.current_state
        prev_state = BACKWARD_TRANSITIONS.get(current)

        if prev_state is None:
            raise StateTransitionError(
                f"当前状态 {state.get_current_state_display()} 不能回退",
                code=ErrorCode.SYSTEM_STATE_ROLLBACK_FORBIDDEN,
            )

        # 更新状态（通过 Repository，含乐观锁版本递增）
        state = self.repository.update(
            state,
            {
                "previous_state": current,
                "current_state": prev_state,
                "state_changed_at": timezone.now(),
            },
        )

        # 记录历史（通过 Repository）
        self.history_repository.create(
            academic_year_id=academic_year_id,
            from_state=current,
            to_state=prev_state,
            transition_type=StateTransitionType.ROLLBACK.value,
            reason=reason,
            operator=operator_user,
        )

        log_state_transition(
            user_id=operator_user.id if operator_user else None,
            academic_year_id=academic_year_id,
            from_state=current,
            to_state=prev_state,
            transition_type="ROLLBACK",
        )
        logger.info(
            "State rollback: year=%s, %s -> %s, reason=%s, operator=%s",
            academic_year_id, current, prev_state, reason,
            operator_user.id if operator_user else None,
        )
        MetricsService.record_state_transition(current, prev_state)
        return state

    # ===== 当前状态查询 =====

    def get_current_state_value(self, academic_year_id: int) -> int:
        """获取学年当前状态值"""
        state = self.get_by_academic_year(academic_year_id)
        return state.current_state

    def is_state(self, academic_year_id: int, expected_state: int) -> bool:
        """判断学年是否处于指定状态"""
        try:
            state = self.get_by_academic_year(academic_year_id)
            return state.current_state == expected_state
        except NotFoundError:
            return False

    # ===== 自动推进（定时任务调用） =====

    @transaction.atomic
    def auto_forward(self, academic_year_id: int) -> SystemState:
        """自动状态推进（由定时任务调用）

        依据 DATABASE.md 7.10：
        - transition_type=AUTO
        - operator_id=NULL
        - 写入 state_history + operation_log

        与 forward() 的区别：
        - 使用 transition_type=AUTO 而非 FORWARD
        - 不需要 operator_user
        - 失败时由调用方（定时任务）重试

        Args:
            academic_year_id: 学年 ID

        Returns:
            更新后的 SystemState
        """
        state = self.get_by_academic_year(academic_year_id)
        current = state.current_state
        next_state = FORWARD_TRANSITIONS.get(current)

        if next_state is None:
            raise StateTransitionError(
                f"当前状态 {state.get_current_state_display()} 不能继续推进",
            )

        # 更新状态
        state = self.repository.update(
            state,
            {
                "previous_state": current,
                "current_state": next_state,
                "state_changed_at": timezone.now(),
            },
        )

        # 记录历史（transition_type=AUTO）
        self.history_repository.create(
            academic_year_id=academic_year_id,
            from_state=current,
            to_state=next_state,
            transition_type=StateTransitionType.AUTO.value,
            operator=None,
        )

        log_state_transition(
            user_id=None,
            academic_year_id=academic_year_id,
            from_state=current,
            to_state=next_state,
            transition_type="AUTO",
        )
        logger.info(
            "Auto state forward: year=%s, %s -> %s",
            academic_year_id, current, next_state,
        )
        MetricsService.record_state_transition(current, next_state)
        return state


class SystemStateScheduleService(BaseService):
    """自动状态切换配置业务服务

    依据 DATABASE.md 7.10 自动时间切换：
    - 定时任务每分钟扫描 system_state_schedule
    - 手动优先（state_changed_at vs scheduled_at）
    - 分布式锁防并发

    回退兼容：
    - 当管理员手动回退状态时，state_changed_at 会更新为当前时间
    - 定时任务检查 state_changed_at < scheduled_at，手动回退后该条件不满足
    - 因此自动切换不会覆盖手动回退操作
    """

    repository = SystemStateScheduleRepository()

    def get_by_academic_year(self, academic_year_id: int) -> SystemStateSchedule:
        schedule = self.repository.get_by_academic_year(academic_year_id)
        if schedule is None:
            raise NotFoundError(
                f"学年 {academic_year_id} 未配置自动状态切换",
            )
        return schedule

    @transaction.atomic
    def init_for_academic_year(self, academic_year_id: int) -> SystemStateSchedule:
        """为学年初始化调度配置（若已存在则返回当前配置）

        供 AcademicYearService.activate 跨聚合调用，避免直接操作 system.models。
        """
        existing = self.repository.get_by_academic_year(academic_year_id)
        if existing:
            return existing
        return self.repository.create(
            academic_year_id=academic_year_id,
            auto_enabled=False,
        )

    @transaction.atomic
    def create(self, validated_data: dict) -> SystemStateSchedule:
        """创建配置（若已存在则抛冲突）"""
        # validated_data 可能用 academic_year（FK 对象）或 academic_year_id
        academic_year = validated_data.get("academic_year") or validated_data.get(
            "academic_year_id"
        )
        academic_year_id = getattr(academic_year, "id", academic_year)

        if academic_year_id and self.repository.exists(academic_year_id=academic_year_id):
            raise BusinessException(
                f"学年 {academic_year_id} 已存在自动状态切换配置",
            )
        return self.repository.create(**validated_data)

    @transaction.atomic
    def update_schedule(
        self, academic_year_id: int, validated_data: dict
    ) -> SystemStateSchedule:
        """更新调度配置

        Args:
            academic_year_id: 学年 ID
            validated_data: 更新字段（first_round_start_at 等）

        Returns:
            更新后的 SystemStateSchedule
        """
        schedule = self.get_by_academic_year(academic_year_id)
        schedule = self.repository.update(schedule, validated_data)
        logger.info(
            "Schedule updated: year=%s, fields=%s",
            academic_year_id, list(validated_data.keys()),
        )
        return schedule

    @transaction.atomic
    def toggle_auto(self, academic_year_id: int, enabled: bool) -> SystemStateSchedule:
        """启停自动切换

        依据 DATABASE.md 7.10：
        - auto_enabled=1 时定时任务扫描
        - auto_enabled=0 时定时任务跳过
        """
        schedule = self.get_by_academic_year(academic_year_id)
        schedule = self.repository.update(schedule, {"auto_enabled": enabled})
        logger.info(
            "Schedule auto toggle: year=%s, enabled=%s", academic_year_id, enabled
        )
        return schedule

    def get_next_transition(
        self, academic_year_id: int
    ) -> dict | None:
        """获取下一次自动切换信息

        依据当前系统状态和调度配置，返回下一次自动切换的时间和目标状态。

        Args:
            academic_year_id: 学年 ID

        Returns:
            {
                "current_state": int,
                "next_state": int,
                "scheduled_at": datetime,
                "time_field": str,
            }
            无下次切换时返回 None
        """
        from apps.system.tasks import STATE_SCHEDULE_FIELDS
        from apps.common.enums import SystemStateValue

        try:
            schedule = self.get_by_academic_year(academic_year_id)
        except NotFoundError:
            return None

        # 获取 SystemState（通过 Repository，不直接访问 ORM）
        state_repo = SystemStateRepository()
        state = state_repo.get_by_academic_year(academic_year_id)
        if state is None:
            return None

        if state.current_state == SystemStateValue.FINISHED.value:
            return None

        time_field = STATE_SCHEDULE_FIELDS.get(state.current_state)
        if not time_field:
            return None

        scheduled_at = getattr(schedule, time_field, None)
        if not scheduled_at:
            return None

        next_state = FORWARD_TRANSITIONS.get(state.current_state)

        return {
            "current_state": state.current_state,
            "next_state": next_state,
            "scheduled_at": scheduled_at,
            "time_field": time_field,
        }
