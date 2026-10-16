"""分配模块 Celery 任务

依据 DATABASE.md 9.1：
- 系统自动分配为异步操作（耗时，不阻塞 API）
- 撤销自动分配为异步操作（批量删除，不阻塞 API）

任务：
- run_auto_assignment: 执行自动分配
- revoke_auto_assignment: 撤销自动分配
"""
from __future__ import annotations

from celery import shared_task

from apps.common.logger import get_logger
from apps.monitoring.decorators import track_time

logger = get_logger("assignments.tasks")


@shared_task(bind=True, name="assignments.run_auto_assignment")
@track_time(metric_type="celery")
def run_auto_assignment(self, academic_year_id: int, triggered_by: int = None):
    """执行自动分配

    调用 AutoAssignmentService.run() 执行实际分配算法。
    DATABASE.md 7.7 / 9.1：系统自动分配为异步操作。

    Args:
        academic_year_id: 学年 ID
        triggered_by: 触发用户 ID

    Returns:
        分配结果摘要
    """
    from apps.assignments.services import AutoAssignmentService

    logger.info(
        "Auto assignment task started: year=%s, by=%s",
        academic_year_id, triggered_by,
    )

    result = AutoAssignmentService.run(
        academic_year_id=academic_year_id,
        triggered_by=triggered_by,
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


@shared_task(bind=True, name="assignments.revoke_auto_assignment")
@track_time(metric_type="celery")
def revoke_auto_assignment(self, academic_year_id: int, auto_assignment_log_id: int, revoked_by: int = None):
    """撤销自动分配

    调用 AutoAssignmentService.revoke() 执行撤销。
    DATABASE.md 7.8 / 9.1：撤销自动分配为异步操作。

    Args:
        academic_year_id: 学年 ID
        auto_assignment_log_id: 自动分配日志 ID
        revoked_by: 撤销用户 ID

    Returns:
        撤销结果摘要
    """
    from apps.assignments.services import AutoAssignmentService

    logger.info(
        "Revoke auto assignment: year=%s, log_id=%s, by=%s",
        academic_year_id, auto_assignment_log_id, revoked_by,
    )

    result = AutoAssignmentService.revoke(
        academic_year_id=academic_year_id,
        auto_assignment_log_id=auto_assignment_log_id,
        revoked_by=revoked_by,
    )

    return {
        "academic_year_id": academic_year_id,
        "auto_assignment_log_id": auto_assignment_log_id,
        "revoked_count": result["revoked_count"],
        "status": "completed",
    }
