"""
申请管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.enums import ApplicationRound, ApplicationStatus
from apps.common.models import TimeStampedModel


class Application(TimeStampedModel):
    """学生申请 - 记录学生选择意向、轮次、审核状态。不可删除、不可取消。"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="applications",
        verbose_name="所属学年",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.PROTECT,
        db_column="student_id",
        related_name="applications",
        verbose_name="申请学生",
    )
    teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.PROTECT,
        db_column="teacher_id",
        related_name="applications",
        verbose_name="申请导师",
    )
    round = models.PositiveSmallIntegerField("轮次", choices=ApplicationRound.choices)
    status = models.PositiveSmallIntegerField(
        "状态",
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    version = models.PositiveIntegerField("乐观锁版本", default=1)

    class Meta:
        db_table = "application"
        verbose_name = "申请"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["academic_year", "teacher", "round", "status"],
                name="idx_year_teacher_round_status",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "student", "round"],
                name="uk_year_student_round",
            ),
        ]

    def __str__(self):
        return f"student {self.student_id} -> teacher {self.teacher_id} round {self.round}"
