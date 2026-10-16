"""系统状态 Celery 任务

依据 PROJECT.md / DATABASE.md 7.10 自动时间切换：
- 每分钟扫描 system_state_schedule
- 手动优先（state_changed_at vs scheduled_at）
- 分布式锁防并发

任务：
- check_and_progress_state: 每分钟扫描，自动推进状态
- auto_close_academic_year: 自动关闭学年

状态机（DATABASE.md）：
    INIT(0) -> FIRST_ROUND_OPEN(1) -> TEACHER_REVIEW(2)
            -> SECOND_ROUND_OPEN(3) -> AUTO_ASSIGN(4) -> FINISHED(5)
"""
from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from apps.monitoring.decorators import track_time

from apps.common.cache_keys import lock_state_auto_transition
from apps.common.enums import StateTransitionType, SystemStateValue
from apps.common.logger import get_logger
from apps.common.lock import DistributedLock, LockAcquisitionError
from apps.system.repositories import (
    SystemStateRepository,
    SystemStateScheduleRepository,
)
from apps.system.services import SystemStateService

logger = get_logger("system.tasks")

# 状态对应的时间字段映射
# Key: 当前状态 → Value: 该状态应该结束（或开始）的时间字段
# 当 now >= scheduled_at 且 state_changed_at < scheduled_at 时，推进到下一状态
STATE_SCHEDULE_FIELDS = {
    SystemStateValue.INIT.value: "first_round_start_at",  # INIT → FIRST_ROUND_OPEN
    SystemStateValue.FIRST_ROUND_OPEN.value: "first_round_end_at",  # FIRST_ROUND_OPEN → TEACHER_REVIEW
    SystemStateValue.TEACHER_REVIEW.value: "teacher_review_end_at",  # TEACHER_REVIEW → SECOND_ROUND_OPEN
    SystemStateValue.SECOND_ROUND_OPEN.value: "second_round_end_at",  # SECOND_ROUND_OPEN → AUTO_ASSIGN
    # AUTO_ASSIGN → FINISHED 由自动分配完成后触发，不需要时间字段
    # FINISHED 是终态，不需要时间字段
}


@shared_task(bind=True, name="system.check_and_progress_state")
@track_time(metric_type="celery")
def check_and_progress_state(self):
    """每分钟扫描，自动推进系统状态

    依据 DATABASE.md 7.10 自动时间切换：
    1. 查询所有 auto_enabled=True 的 schedule
    2. 对每个 schedule，检查当前状态对应的时间字段
    3. 如果 scheduled_at <= now 且 state_changed_at < scheduled_at，则推进
    4. 使用分布式锁防并发

    Returns:
        推进的学年列表
    """
    now = timezone.now()
    progressed_years = []
    service = SystemStateService()
    state_repo = SystemStateRepository()
    schedule_repo = SystemStateScheduleRepository()

    # 查询所有启用自动切换的 schedule
    schedules = schedule_repo.list_auto_enabled()

    logger.info("Auto state check: %d schedules to scan", schedules.count())

    for schedule in schedules:
        academic_year_id = schedule.academic_year_id

        # 获取当前系统状态（通过 Repository）
        state = state_repo.get_by_academic_year(academic_year_id)
        if state is None:
            logger.warning(
                "SystemState not found for year=%s, skip", academic_year_id
            )
            continue

        # FINISHED 状态不需要推进
        if state.current_state == SystemStateValue.FINISHED.value:
            continue

        # 获取当前状态对应的调度时间字段
        time_field = STATE_SCHEDULE_FIELDS.get(state.current_state)
        if not time_field:
            continue

        scheduled_at = getattr(schedule, time_field, None)
        if not scheduled_at:
            continue

        # 手动优先：如果 state_changed_at >= scheduled_at，说明用户已手动操作
        if state.state_changed_at >= scheduled_at:
            continue

        # 检查是否到达调度时间
        if now < scheduled_at:
            continue

        # 使用分布式锁防并发
        lock_key = lock_state_auto_transition(academic_year_id)
        lock = DistributedLock(lock_key, ttl=30)

        if not lock.acquire():
            logger.info(
                "Auto transition lock busy: year=%s, skip", academic_year_id
            )
            continue

        try:
            # 再次检查状态（防止并发期间状态已被修改）
            state.refresh_from_db()
            if state.current_state == SystemStateValue.FINISHED.value:
                continue

            # 使用 auto_forward（transition_type=AUTO, operator=NULL）
            service.auto_forward(academic_year_id)
            progressed_years.append(academic_year_id)

            logger.info(
                "Auto state progressed: year=%s, state=%s -> next, scheduled_at=%s",
                academic_year_id, state.current_state, scheduled_at,
            )

        except Exception as exc:
            logger.error(
                "Auto state progress failed: year=%s, error=%s",
                academic_year_id, exc,
            )
        finally:
            lock.release()

    if progressed_years:
        logger.info("Auto state progressed years: %s", progressed_years)

    return progressed_years


@shared_task(bind=True, name="system.auto_close_academic_year")
@track_time(metric_type="celery")
def auto_close_academic_year(self, academic_year_id: int):
    """自动关闭学年

    当系统状态进入 FINISHED 后，自动关闭学年。

    Args:
        academic_year_id: 学年 ID
    """
    from apps.academic_year.repositories import AcademicYearRepository
    from apps.common.enums import AcademicYearStatus

    logger.info("Auto close academic year: %s", academic_year_id)

    year_repo = AcademicYearRepository()

    try:
        year = year_repo.get_by_id_or_none(academic_year_id)
        if year is None:
            logger.error("Academic year not found: %s", academic_year_id)
            return {"academic_year_id": academic_year_id, "status": "not_found"}

        if year.status == AcademicYearStatus.ARCHIVED.value:
            logger.info("Year already archived: %s", academic_year_id)
            return {"academic_year_id": academic_year_id, "status": "already_archived"}

        year_repo.update(year, {"status": AcademicYearStatus.ARCHIVED.value})

        logger.info("Academic year archived: %s", academic_year_id)
        return {"academic_year_id": academic_year_id, "status": "archived"}

    except Exception as exc:
        logger.error(
            "Auto close failed: year=%s, error=%s", academic_year_id, exc
        )
        raise


@shared_task(bind=True, name="system.run_auto_assignment")
@track_time(metric_type="celery")
def run_auto_assignment(self, academic_year_id: int, triggered_by: int = None):
    """触发自动分配

    当系统状态进入 AUTO_ASSIGN 后，触发自动分配任务。
    调用 AutoAssignmentService.run() 执行实际分配。

    Args:
        academic_year_id: 学年 ID
        triggered_by: 触发用户 ID
    """
    from apps.assignments.services import AutoAssignmentService

    logger.info(
        "Auto assignment triggered: year=%s, by=%s", academic_year_id, triggered_by
    )

    result = AutoAssignmentService.run(
        academic_year_id=academic_year_id, triggered_by=triggered_by
    )

    return {
        "academic_year_id": academic_year_id,
        "log_id": result.log_id,
        "total_unassigned": result.total_unassigned,
        "assigned_count": result.assigned_count,
        "failed_count": result.failed_count,
        "is_all_assigned": result.is_all_assigned,
        "status": "completed",
    }
