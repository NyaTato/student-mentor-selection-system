"""
分配结果 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.enums import AdmissionSource, AutoAssignmentStatus
from apps.common.models import TimeStampedModel


class AutoAssignmentLog(TimeStampedModel):
    """自动分配日志 - 记录每次自动分配的元数据和结果，支持整批撤销"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="auto_assignment_logs",
        verbose_name="所属学年",
    )
    status = models.PositiveSmallIntegerField(
        "状态",
        choices=AutoAssignmentStatus.choices,
        default=AutoAssignmentStatus.RUNNING.value,
    )
    total_unassigned = models.PositiveIntegerField("未匹配学生数", default=0)
    assigned_count = models.PositiveIntegerField("实际分配数", default=0)
    failed_count = models.PositiveIntegerField("分配失败数", default=0)
    triggered_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        db_column="triggered_by",
        related_name="triggered_auto_assignments",
        verbose_name="触发管理员",
    )
    started_at = models.DateTimeField("开始时间")
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    is_revoked = models.BooleanField("是否已撤销", default=False)
    revoked_at = models.DateTimeField("撤销时间", null=True, blank=True)
    revoked_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        db_column="revoked_by",
        related_name="revoked_auto_assignments",
        null=True,
        blank=True,
        verbose_name="撤销操作人",
    )

    class Meta:
        db_table = "auto_assignment_log"
        verbose_name = "自动分配日志"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["academic_year", "created_at"],
                name="idx_autoassign_year_created",
            ),
            models.Index(fields=["status"], name="idx_autoassign_status"),
            models.Index(fields=["is_revoked"], name="idx_revoked"),
        ]

    def __str__(self):
        return f"auto-assign {self.id} year {self.academic_year_id}"


class Admission(TimeStampedModel):
    """录取结果 - 系统核心产出，记录最终分配结果和来源。无软删除。"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="admissions",
        verbose_name="所属学年",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.PROTECT,
        db_column="student_id",
        related_name="admissions",
        verbose_name="录取学生",
    )
    teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.PROTECT,
        db_column="teacher_id",
        related_name="admissions",
        verbose_name="录取导师",
    )
    source = models.PositiveSmallIntegerField("来源", choices=AdmissionSource.choices)
    application = models.ForeignKey(
        "applications.Application",
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="admission",
        null=True,
        blank=True,
        verbose_name="对应申请",
    )
    auto_assignment_log = models.ForeignKey(
        "assignments.AutoAssignmentLog",
        on_delete=models.CASCADE,
        db_column="auto_assignment_log_id",
        related_name="admissions",
        null=True,
        blank=True,
        verbose_name="自动分配批次",
    )
    version = models.PositiveIntegerField("乐观锁版本", default=1)

    class Meta:
        db_table = "admission"
        verbose_name = "录取"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["academic_year", "teacher"],
                name="idx_year_teacher",
            ),
            models.Index(
                fields=["auto_assignment_log"],
                name="idx_auto_log",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "student"],
                name="uk_year_student",
            ),
        ]

    def __str__(self):
        return f"student {self.student_id} -> teacher {self.teacher_id} ({self.get_source_display()})"
