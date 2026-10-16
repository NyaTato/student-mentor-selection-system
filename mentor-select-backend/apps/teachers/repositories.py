"""
导师管理 Repository
"""
from __future__ import annotations

from django.db.models import Count, QuerySet

from apps.common.repositories import BaseRepository
from apps.teachers.models import TeacherProfile, TeacherQuota


class TeacherProfileRepository(BaseRepository):
    """导师档案 Repository"""

    model = TeacherProfile

    def get_queryset(self):
        return self.model.objects.select_related("user").all()

    def get_by_user_id(self, user_id: int) -> TeacherProfile | None:
        """按 user_id 查询"""
        return self.get_queryset().filter(user_id=user_id).first()

    def get_by_teacher_number(self, teacher_number: str) -> TeacherProfile | None:
        """按工号查询"""
        return self.get_queryset().filter(teacher_number=teacher_number).first()


class TeacherQuotaRepository(BaseRepository):
    """导师名额 Repository"""

    model = TeacherQuota

    def get_queryset(self):
        return self.model.objects.select_related("academic_year", "teacher").all()

    def get_by_year_and_teacher(
        self, academic_year_id: int, teacher_id: int
    ) -> TeacherQuota | None:
        """按学年+导师查询"""
        return self.get_queryset().filter(
            academic_year_id=academic_year_id,
            teacher_id=teacher_id,
        ).first()

    def get_for_update_by_year_and_teacher(
        self, academic_year_id: int, teacher_id: int
    ) -> TeacherQuota | None:
        """按学年+导师查询（带行锁，防 TOCTOU 并发超卖）

        必须在 transaction.atomic 内调用。
        """
        return (
            self.model.objects.select_for_update()
            .filter(
                academic_year_id=academic_year_id,
                teacher_id=teacher_id,
                deleted_at__isnull=True,
            )
            .first()
        )

    def list_by_year(self, academic_year_id: int):
        """按学年查询所有名额"""
        return self.get_queryset().filter(academic_year_id=academic_year_id)

    def list_by_teacher(self, teacher_id: int):
        """按导师查询所有学年的名额"""
        return self.get_queryset().filter(teacher_id=teacher_id)

    def list_with_remaining(
        self,
        academic_year_id: int,
        admitted_map: dict[int, int] | None = None,
        for_update: bool = False,
    ) -> list[dict]:
        """查询导师名额及剩余容量（深方法：封装 max_quota - admitted 计算）

        依据 DATABASE.md 7.7 第 5 步：
        按剩余名额降序 + teacher_number 升序排序。

        通过 AdmissionRepository 获取已录取数，避免本 Repository 反向依赖
        assignments 模块的 Model（保持模块边界清晰）。

        Args:
            academic_year_id: 学年 ID
            admitted_map: {teacher_id: admitted_count}，若为 None 则通过
                AdmissionRepository 查询（调用方也可预先查询后传入，避免重复查询）
            for_update: 是否加行锁（自动分配场景）

        Returns:
            [{"teacher_id", "teacher_number", "name", "max_quota",
              "admitted_count", "remaining_quota"}]
        """
        qs = self.get_queryset().filter(
            academic_year_id=academic_year_id,
            deleted_at__isnull=True,
        )
        if for_update:
            qs = qs.select_for_update()
            # 固定锁顺序：先锁 teacher_quota 行，再做 admission 当前读计数。
            # 若先查 admitted_map（普通读）再锁 quota，在 MySQL REPEATABLE READ
            # 下会读到事务早期快照的过期计数，导致并发超卖。
            quota_rows = list(qs)
        else:
            quota_rows = list(qs)

        # 若未提供 admitted_map，通过 AdmissionRepository 查询（保持模块边界）
        if admitted_map is None:
            from apps.assignments.repositories import AdmissionRepository

            admission_repo = AdmissionRepository()
            admitted_map = admission_repo.get_admitted_map(
                academic_year_id, for_update=for_update
            )

        teachers = []
        for quota in quota_rows:
            admitted = admitted_map.get(quota.teacher_id, 0)
            remaining = quota.max_quota - admitted
            teachers.append({
                "teacher_id": quota.teacher_id,
                "teacher_number": quota.teacher.teacher_number,
                "name": quota.teacher.name,
                "max_quota": quota.max_quota,
                "admitted_count": admitted,
                "remaining_quota": remaining,
            })

        # 按剩余名额降序 + teacher_number 升序排序
        teachers.sort(key=lambda t: (-t["remaining_quota"], t["teacher_number"]))
        return teachers
