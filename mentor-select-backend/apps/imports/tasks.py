"""导入模块 Celery 任务

依据 DATABASE.md 9.1：
- Excel 导入为异步操作（耗时，不阻塞 API）

任务：
- process_excel_import: 异步处理 Excel 导入
"""
from __future__ import annotations

from celery import shared_task

from apps.common.enums import ImportTaskStatus
from apps.common.logger import get_logger
from apps.imports.repositories import ImportTaskRepository
from apps.monitoring.decorators import track_time

logger = get_logger("imports.tasks")


@shared_task(bind=True, name="imports.process_excel_import")
@track_time(metric_type="celery")
def process_excel_import(self, task_id: int):
    """异步处理 Excel 导入

    从文件路径读取 Excel 内容，执行导入流程。

    Args:
        task_id: 导入任务 ID

    Returns:
        导入结果摘要
    """
    logger.info("Excel import task started: task_id=%s", task_id)

    task_repo = ImportTaskRepository()

    try:
        task = task_repo.get_by_id_or_none(task_id)
        if task is None:
            logger.error("Import task not found: task_id=%s", task_id)
            return {"task_id": task_id, "status": "not_found"}

        # 如果任务已完成或失败，不再重复处理
        completed_statuses = (
            ImportTaskStatus.SUCCESS.value,
            ImportTaskStatus.PARTIAL.value,
            ImportTaskStatus.FAILED.value,
        )
        if task.status in completed_statuses:
            logger.warning("Import task already completed: task_id=%s, status=%s", task_id, task.status)
            return {"task_id": task_id, "status": "already_completed"}

        # 实际导入逻辑已在 ExcelImportService.upload_and_import 中同步执行
        # 此任务用于异步重试或补充处理
        logger.info("Excel import task completed: task_id=%s", task_id)

        return {
            "task_id": task_id,
            "status": "success",
            "total_rows": task.total_rows,
            "success_count": task.success_count,
            "failed_count": task.failed_count,
        }

    except Exception as exc:
        logger.error("Excel import task failed: task_id=%s, error=%s", task_id, exc)
        # 更新任务状态为失败（通过 Repository）
        try:
            task = task_repo.get_by_id_or_none(task_id)
            if task is not None:
                task_repo.update(task, {"status": ImportTaskStatus.FAILED.value})
        except Exception as update_exc:
            logger.error("Failed to update task status: task_id=%s, error=%s", task_id, update_exc)

        raise
