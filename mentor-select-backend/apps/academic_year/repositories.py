"""
学年管理 Repository
"""
from apps.academic_year.models import AcademicYear
from apps.common.enums import AcademicYearStatus
from apps.common.repositories import BaseRepository


class AcademicYearRepository(BaseRepository):
    """学年 Repository"""

    model = AcademicYear

    def get_queryset(self):
        # SoftDeleteManager 已过滤软删除
        return self.model.objects.all()

    def get_by_name(self, name: str) -> AcademicYear | None:
        """按学年名称查询"""
        return self.get_queryset().filter(name=name).first()

    def get_active(self) -> AcademicYear | None:
        """查询当前激活的学年（全局唯一 ACTIVE）"""
        return self.get_queryset().filter(
            status=AcademicYearStatus.ACTIVE.value
        ).first()

    def has_active(self) -> bool:
        """是否存在激活的学年"""
        return self.get_queryset().filter(
            status=AcademicYearStatus.ACTIVE.value
        ).exists()
