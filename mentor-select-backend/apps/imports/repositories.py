"""导入管理 Repository

提供 ImportTask 和 ImportLog 的数据访问能力。
支持创建、更新任务状态，以及批量创建日志。

依据 DATABASE.md 7.9 Excel 导入流程：
- ImportTask: 可写（创建任务、更新状态）
- ImportLog: 只追加（每行一条记录，不可修改、不可删除）
"""
from __future__ import annotations

from django.db.models import QuerySet

from apps.common.repositories import AppendOnlyRepositoryBase, BaseRepository
from apps.imports.models import ImportLog, ImportTask


class ImportTaskRepository(BaseRepository):
    """导入任务 Repository（可写）"""

    model = ImportTask

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related(
            "academic_year", "triggered_by"
        ).all()

    def list_by_academic_year(self, academic_year_id: int) -> QuerySet:
        """按学年查询导入任务"""
        return self.get_queryset().filter(academic_year_id=academic_year_id)

    def list_by_status(self, status: int) -> QuerySet:
        """按状态查询导入任务"""
        return self.get_queryset().filter(status=status)

    def list_by_role(self, role: int) -> QuerySet:
        """按角色查询导入任务"""
        return self.get_queryset().filter(role=role)


class ImportLogRepository(AppendOnlyRepositoryBase):
    """导入日志 Repository（只追加）

    LSP 合规：继承 AppendOnlyRepositoryBase，不暴露 update/delete 方法。
    """

    model = ImportLog

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related("task", "created_user").all()

    def list_by_task(self, task_id: int) -> QuerySet:
        """按任务查询导入日志"""
        return self.get_queryset().filter(task_id=task_id)

    def list_by_task_and_status(self, task_id: int, status: int) -> QuerySet:
        """按任务+状态查询导入日志"""
        return self.get_queryset().filter(task_id=task_id, status=status)

    def list_failures(self, task_id: int) -> QuerySet:
        """查询任务的失败日志"""
        from apps.common.enums import ImportRowStatus

        return self.get_queryset().filter(
            task_id=task_id, status=ImportRowStatus.FAILED.value
        )

    def bulk_create_logs(self, logs: list[ImportLog]) -> list[ImportLog]:
        """批量创建日志"""
        return self.model.objects.bulk_create(logs)
