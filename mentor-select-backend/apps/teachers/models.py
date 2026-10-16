"""
导师管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.models import BaseModel
from apps.common.models.mixins import AllObjectsManager, SoftDeleteManager


class TeacherProfile(BaseModel):
    """导师档案 - 与 User 一对一，共享主键"""

    user = models.OneToOneField(
        "users.User",
        on_delete=models.PROTECT,
        primary_key=True,
        db_column="user_id",
        related_name="teacher_profile",
        verbose_name="用户",
    )
    teacher_number = models.CharField("工号", max_length=32, unique=True)
    name = models.CharField("姓名", max_length=64)
    college = models.CharField("学院", max_length=128)
    title = models.CharField("职称", max_length=64, default="")
    research_area = models.CharField("研究方向", max_length=512, default="")
    profile = models.TextField("个人简介", null=True, blank=True)
    graduation_direction = models.CharField(
        "毕业设计方向", max_length=512, null=True, blank=True
    )
    thesis_topic = models.CharField("论文题目", max_length=512, null=True, blank=True)
    student_requirement = models.CharField(
        "对学生要求", max_length=512, null=True, blank=True
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "teacher_profile"
        verbose_name = "导师档案"
        verbose_name_plural = verbose_name
        ordering = ["-user_id"]

    def __str__(self):
        return f"{self.teacher_number} {self.name}"


class TeacherQuota(BaseModel):
    """导师招生名额 - 按学年独立设置"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="teacher_quotas",
        verbose_name="所属学年",
    )
    teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.PROTECT,
        db_column="teacher_id",
        related_name="quotas",
        verbose_name="导师",
    )
    max_quota = models.PositiveSmallIntegerField("招生名额上限", default=0)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "teacher_quota"
        verbose_name = "导师名额"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "teacher"],
                name="uk_year_teacher",
            ),
        ]
        indexes = [
            models.Index(fields=["academic_year"], name="idx_year"),
        ]

    def __str__(self):
        return f"{self.teacher_id} quota {self.max_quota}"
