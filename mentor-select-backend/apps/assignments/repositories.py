"""
分配结果 Repository

Admission：录取结果，由业务流程创建（申请通过 / 人工分配 / 自动分配）。
AutoAssignmentLog：自动分配日志，由自动分配服务创建，可更新状态/撤销。
"""
from __future__ import annotations

from django.db.models import Count

from apps.assignments.models import Admission, AutoAssignmentLog
from apps.common.repositories import BaseRepository


class AdmissionRepository(BaseRepository):
    """录取结果 Repository

    录取结果由业务流程创建（申请通过 / 人工分配 / 自动分配），
    本阶段不通过 API 直接创建/修改/删除。
    """

    model = Admission

    def get_queryset(self):
        return self.model.objects.select_related(
            "academic_year", "student", "teacher", "application",
            "auto_assignment_log",
        ).all()

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询录取结果"""
        return self.get_queryset().filter(academic_year_id=academic_year_id)

    def list_by_teacher(self, teacher_id: int, academic_year_id: int | None = None):
        """按导师查询录取结果"""
        qs = self.get_queryset().filter(teacher_id=teacher_id)
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs

    def list_by_student(self, student_id: int):
        """按学生查询录取结果"""
        return self.get_queryset().filter(student_id=student_id)

    def get_by_year_student(self, academic_year_id: int, student_id: int):
        """按学年+学生查询录取结果（每学年每学生唯一）"""
        return self.get_queryset().filter(
            academic_year_id=academic_year_id,
            student_id=student_id,
        ).first()

    def get_by_year_student_for_update(
        self, academic_year_id: int, student_id: int
    ) -> Admission | None:
        """按学年+学生加行锁查询（不存在返回 None）

        必须在 transaction.atomic 内调用。
        """
        return (
            self.model.objects.select_for_update()
            .filter(
                academic_year_id=academic_year_id,
                student_id=student_id,
            )
            .first()
        )

    def lock_student_row(self, student_id: int):
        """锁定学生行（固定锁顺序第 1 步）

        串行化「同一学生」的占用判定，避免同一学生并发产生两条录取。
        必须在 transaction.atomic 内调用；不存在返回 None。
        """
        from apps.students.models import StudentProfile

        return (
            StudentProfile.objects.select_for_update()
            .filter(pk=student_id)
            .first()
        )

    def delete_by_year_student(self, academic_year_id: int, student_id: int) -> int:
        """按学年+学生删除录取记录

        .. deprecated::
            取消第二轮申请**不再**调用本方法 —— 它会按学生删除任意来源的
            录取记录（包括人工分配 / 自动分配）。取消路径请使用
            :meth:`delete_by_application`，只删除与该申请精确关联的记录。
            本方法保留仅为兼容历史调用方，新代码不应使用。

        Returns:
            删除的记录数
        """
        deleted_count, _ = self.model.objects.filter(
            academic_year_id=academic_year_id,
            student_id=student_id,
        ).delete()
        return deleted_count

    def delete_by_application(
        self, application_id: int, sources: tuple[int, ...] | None = None
    ) -> int:
        """按申请精确删除录取记录（取消第二轮申请，恰好释放一个名额）

        Args:
            application_id: 申请 ID
            sources: 可选来源白名单，只删除这些来源的记录

        Returns:
            删除的记录数
        """
        qs = self.model.objects.filter(application_id=application_id)
        if sources:
            qs = qs.filter(source__in=list(sources))
        deleted_count, _ = qs.delete()
        return deleted_count

    def count_by_teacher(self, teacher_id: int, academic_year_id: int) -> int:
        """统计导师在某学年的已录取人数（普通快照读）"""
        return self.model.objects.filter(
            teacher_id=teacher_id,
            academic_year_id=academic_year_id,
        ).count()

    def count_by_teacher_current(self, teacher_id: int, academic_year_id: int) -> int:
        """统计导师在某学年的已录取人数（**当前读**）

        在 MySQL REPEATABLE READ 下，同一事务内先执行过普通 SELECT 后，
        后续普通 SELECT 会复用旧快照，即使已持有 quota 行锁也会读到过期计数。
        本方法用 ``select_for_update`` 物化查询结果，强制走当前读（locking read），
        从而看到其它事务已提交的录取记录。

        必须在 transaction.atomic 内调用。
        """
        rows = list(
            self.model.objects.select_for_update().filter(
                teacher_id=teacher_id,
                academic_year_id=academic_year_id,
            )
        )
        return len(rows)

    # ===== 聚合查询（深方法：封装统计逻辑） =====

    def list_assigned_student_ids(self, academic_year_id: int) -> list[int]:
        """查询学年下已录取的学生 ID 列表"""
        return list(
            self.model.objects.filter(
                academic_year_id=academic_year_id
            ).values_list("student_id", flat=True)
        )

    def get_admitted_map(
        self, academic_year_id: int, for_update: bool = False
    ) -> dict[int, int]:
        """查询学年下各导师已录取数（{teacher_id: admitted_count}）

        Args:
            for_update: True 时使用**当前读**（select_for_update 物化），
                避免 MySQL REPEATABLE READ 下读到事务早期快照的过期计数。
                自动分配在加锁后必须使用该模式。必须在 transaction.atomic 内调用。
        """
        if for_update:
            counts: dict[int, int] = {}
            for row in self.model.objects.select_for_update().filter(
                academic_year_id=academic_year_id
            ):
                counts[row.teacher_id] = counts.get(row.teacher_id, 0) + 1
            return counts

        qs = (
            self.model.objects.filter(academic_year_id=academic_year_id)
            .values("teacher_id")
            .annotate(admitted=Count("id"))
        )
        return {item["teacher_id"]: item["admitted"] for item in qs}

    def count_group_by_source(self, academic_year_id: int) -> list[dict]:
        """按来源分组计数"""
        return list(
            self.model.objects.filter(academic_year_id=academic_year_id)
            .values("source")
            .annotate(count=Count("id"))
        )

    def delete_auto_assigned_by_log(self, auto_assignment_log_id: int) -> int:
        """删除指定自动分配日志的 AUTO_ASSIGNED 录取记录（撤销用）

        Returns:
            删除的记录数
        """
        from apps.common.enums import AdmissionSource

        deleted_count, _ = self.model.objects.filter(
            auto_assignment_log_id=auto_assignment_log_id,
            source=AdmissionSource.AUTO_ASSIGNED.value,
        ).delete()
        return deleted_count


class AutoAssignmentLogRepository(BaseRepository):
    """自动分配日志 Repository

    日志由自动分配任务创建，可更新状态（RUNNING → SUCCESS/PARTIAL/FAILED/REVOKED）。
    """

    model = AutoAssignmentLog

    def get_queryset(self):
        return self.model.objects.select_related(
            "academic_year", "triggered_by", "revoked_by"
        ).all()

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询自动分配日志"""
        return self.get_queryset().filter(academic_year_id=academic_year_id)

    def get_by_id_for_update(self, pk: int) -> AutoAssignmentLog | None:
        """按主键加行锁查询日志（不存在返回 None）

        必须在 transaction.atomic 内调用。撤销自动分配时用于串行化，
        防止与「正在运行的分配任务」并发。
        """
        return (
            self.model.objects.select_for_update()
            .filter(pk=pk)
            .first()
        )

    def get_running_by_year(self, academic_year_id: int):
        """查询学年下运行中的自动分配日志"""
        from apps.common.enums import AutoAssignmentStatus

        return self.get_queryset().filter(
            academic_year_id=academic_year_id,
            status=AutoAssignmentStatus.RUNNING.value,
        )
