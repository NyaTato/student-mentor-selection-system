"""
系统状态 Repository
"""
from __future__ import annotations

from django.db.models import QuerySet

from apps.common.repositories import AppendOnlyRepositoryBase, BaseRepository
from apps.system.models import StateHistory, SystemState, SystemStateSchedule


class SystemStateRepository(BaseRepository):
    """系统状态 Repository

    注意：SystemState 不支持软删除，由系统状态机管理生命周期。
    """

    model = SystemState

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related("academic_year").all()

    def get_by_academic_year(self, academic_year_id: int) -> SystemState | None:
        """按学年查询系统状态"""
        return self.get_queryset().filter(academic_year_id=academic_year_id).first()


class SystemStateScheduleRepository(BaseRepository):
    """自动状态切换配置 Repository"""

    model = SystemStateSchedule

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related("academic_year").all()

    def get_by_academic_year(self, academic_year_id: int) -> SystemStateSchedule | None:
        """按学年查询配置"""
        return self.get_queryset().filter(academic_year_id=academic_year_id).first()

    def list_auto_enabled(self) -> QuerySet:
        """查询所有启用自动切换的配置"""
        return self.get_queryset().filter(auto_enabled=True)


class StateHistoryRepository(AppendOnlyRepositoryBase):
    """状态变更历史 Repository（只追加）

    LSP 合规：继承 AppendOnlyRepositoryBase，不暴露 update/delete 方法。
    """

    model = StateHistory

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related("academic_year", "operator").all()

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询历史"""
        return self.get_queryset().filter(academic_year_id=academic_year_id)
