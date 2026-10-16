"""
学生管理 Repository

模块边界说明：
本 Repository 仅操作 students 模块的 Model，不反向依赖 assignments 模块。
"未分配学生"查询需要排除已录取学生，该数据由 Service 层通过
AdmissionRepository.list_assigned_student_ids() 获取后传入本 Repository，
保持 Repository 层的模块独立性。
"""
from __future__ import annotations

from apps.common.repositories import BaseRepository
from apps.students.models import StudentProfile


class StudentProfileRepository(BaseRepository):
    """学生档案 Repository"""

    model = StudentProfile

    def get_queryset(self):
        return self.model.objects.select_related("user").all()

    def get_by_user_id(self, user_id: int) -> StudentProfile | None:
        """按 user_id 查询"""
        return self.get_queryset().filter(user_id=user_id).first()

    def get_by_student_number(self, student_number: str) -> StudentProfile | None:
        """按学号查询"""
        return self.get_queryset().filter(student_number=student_number).first()

    def list_unassigned(
        self,
        excluded_user_ids: list[int] | None = None,
    ) -> list[StudentProfile]:
        """查询未分配学生列表（排除已录取学生）

        依据 DATABASE.md 7.7 第 4 步。
        按学号升序排序。

        模块边界：excluded_user_ids 由 Service 层通过 AdmissionRepository
        获取后传入，本 Repository 不反向依赖 assignments 模块。

        Args:
            excluded_user_ids: 已录取学生的 user_id 列表（由 Service 层提供）

        Returns:
            未分配学生列表
        """
        qs = self.get_queryset()
        if excluded_user_ids:
            qs = qs.exclude(user_id__in=excluded_user_ids)
        return list(qs.order_by("student_number"))

    def count_unassigned(
        self,
        excluded_user_ids: list[int] | None = None,
    ) -> int:
        """统计未分配学生数（排除已录取学生）

        模块边界：excluded_user_ids 由 Service 层通过 AdmissionRepository
        获取后传入，本 Repository 不反向依赖 assignments 模块。

        Args:
            excluded_user_ids: 已录取学生的 user_id 列表（由 Service 层提供）
        """
        qs = self.get_queryset()
        if excluded_user_ids:
            qs = qs.exclude(user_id__in=excluded_user_ids)
        return qs.count()
