"""
申请管理 Repository
"""
from __future__ import annotations

from django.db.models import Count, QuerySet

from apps.applications.models import Application
from apps.common.enums import ApplicationRound, ApplicationStatus
from apps.common.repositories import BaseRepository


class ApplicationRepository(BaseRepository):
    """申请 Repository

    注意：Application 模型继承自 TimeStampedModel，无软删除字段，
    申请不可删除（业务规则 R2）。
    """

    model = Application

    def get_queryset(self) -> QuerySet:
        return self.model.objects.select_related(
            "academic_year", "student", "teacher"
        ).all()

    def get_by_id(self, pk: int) -> Application:
        return super().get_by_id(pk)

    def get_by_id_for_update(self, pk: int) -> Application | None:
        """按主键加行锁查询（不存在返回 None）

        必须在 transaction.atomic 内调用。用于审核 / 取消 / 第一轮修改，
        串行化对同一申请行的状态变更（防重复审核与 TOCTOU）。
        """
        return (
            self.model.objects.select_for_update()
            .filter(pk=pk)
            .first()
        )

    def get_by_year_student_round_for_update(
        self,
        academic_year_id: int,
        student_id: int,
        round_value: int,
    ) -> Application | None:
        """按学年+学生+轮次加行锁查询（用于第一轮「修改」路径）

        必须在 transaction.atomic 内调用。
        """
        return (
            self.model.objects.select_for_update()
            .filter(
                academic_year_id=academic_year_id,
                student_id=student_id,
                round=round_value,
            )
            .first()
        )

    def get_by_year_student_round(
        self,
        academic_year_id: int,
        student_id: int,
        round_value: int,
    ) -> Application | None:
        """按学年+学生+轮次查询"""
        return self.get_queryset().filter(
            academic_year_id=academic_year_id,
            student_id=student_id,
            round=round_value,
        ).first()

    def list_by_student(self, student_id: int, academic_year_id: int | None = None):
        """查询学生的所有申请"""
        qs = self.get_queryset().filter(student_id=student_id)
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs

    def list_by_teacher(
        self,
        teacher_id: int,
        academic_year_id: int | None = None,
        round_value: int | None = None,
        status: int | None = None,
    ):
        """查询导师收到的申请"""
        qs = self.get_queryset().filter(teacher_id=teacher_id)
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        if round_value:
            qs = qs.filter(round=round_value)
        if status:
            qs = qs.filter(status=status)
        return qs

    def list_pending_by_teacher(self, teacher_id: int, academic_year_id: int, round_value: int):
        """查询导师在某学年某轮次的待处理申请"""
        return self.get_queryset().filter(
            teacher_id=teacher_id,
            academic_year_id=academic_year_id,
            round=round_value,
            status=ApplicationStatus.PENDING.value,
        )

    def count_approved_by_teacher(
        self, teacher_id: int, academic_year_id: int, round_value: int | None = None
    ) -> int:
        """统计导师在某学年（某轮次）已通过的申请数"""
        qs = self.get_queryset().filter(
            teacher_id=teacher_id,
            academic_year_id=academic_year_id,
            status=ApplicationStatus.APPROVED.value,
        )
        if round_value:
            qs = qs.filter(round=round_value)
        return qs.count()

    def has_approved_application(
        self, student_id: int, academic_year_id: int, round_value: int | None = None
    ) -> bool:
        """判断学生是否在某学年（某轮次）已有通过的申请"""
        qs = self.get_queryset().filter(
            student_id=student_id,
            academic_year_id=academic_year_id,
            status=ApplicationStatus.APPROVED.value,
        )
        if round_value:
            qs = qs.filter(round=round_value)
        return qs.exists()

    def get_first_round_status(self, student_id: int, academic_year_id: int) -> int | None:
        """查询学生第一轮申请的状态

        返回 None 表示无第一轮申请。
        """
        app = self.get_by_year_student_round(
            academic_year_id, student_id, ApplicationRound.FIRST_ROUND.value
        )
        return app.status if app else None

    # ===== 聚合查询（深方法：封装统计逻辑） =====

    def count_group_by_status(self, academic_year_id: int) -> list[dict]:
        """按状态分组计数"""
        return list(
            self.model.objects.filter(academic_year_id=academic_year_id)
            .values("status")
            .annotate(count=Count("id"))
        )

    def count_group_by_round(self, academic_year_id: int) -> list[dict]:
        """按轮次分组计数"""
        return list(
            self.model.objects.filter(academic_year_id=academic_year_id)
            .values("round")
            .annotate(count=Count("id"))
        )

    def count_group_by_teacher(self, academic_year_id: int) -> list[dict]:
        """按导师分组计数（含导师信息）

        返回字段已归一化（teacher_number / teacher_name），
        避免 ORM 路径（teacher__teacher_number）泄漏到 Service 层。
        """
        rows = (
            self.model.objects.filter(academic_year_id=academic_year_id)
            .values("teacher_id", "teacher__teacher_number", "teacher__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [
            {
                "teacher_id": row["teacher_id"],
                "teacher_number": row["teacher__teacher_number"],
                "teacher_name": row["teacher__name"],
                "count": row["count"],
            }
            for row in rows
        ]
