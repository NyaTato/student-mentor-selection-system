"""
学生管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.models import BaseModel
from apps.common.models.mixins import AllObjectsManager, SoftDeleteManager


class StudentProfile(BaseModel):
    """学生档案 - 与 User 一对一，共享主键"""

    user = models.OneToOneField(
        "users.User",
        on_delete=models.PROTECT,
        primary_key=True,
        db_column="user_id",
        related_name="student_profile",
        verbose_name="用户",
    )
    student_number = models.CharField("学号", max_length=32, unique=True)
    name = models.CharField("姓名", max_length=64)
    major = models.CharField("专业", max_length=128)
    class_name = models.CharField("班级", max_length=64)
    department = models.CharField("院系", max_length=128, null=True, blank=True)
    # v2 API 学生详情/自助改电话使用；导师仅在存在真实申请/录取关系时可见
    phone = models.CharField("电话号码", max_length=20, null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "student_profile"
        verbose_name = "学生档案"
        verbose_name_plural = verbose_name
        ordering = ["-user_id"]

    def __str__(self):
        return f"{self.student_number} {self.name}"
