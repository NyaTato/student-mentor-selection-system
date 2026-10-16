"""
学年管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models
from django.db.models import Q

from apps.common.enums import AcademicYearStatus
from apps.common.models import BaseModel
from apps.common.models.mixins import AllObjectsManager, SoftDeleteManager


class AcademicYear(BaseModel):
    """学年 - 按学年管理，每年独立开启导师选择"""

    name = models.CharField("学年名称", max_length=16, unique=True)
    start_year = models.PositiveSmallIntegerField("开始年份")
    end_year = models.PositiveSmallIntegerField("结束年份")
    status = models.PositiveSmallIntegerField(
        "状态", choices=AcademicYearStatus.choices, default=AcademicYearStatus.INACTIVE
    )
    activated_at = models.DateTimeField("激活时间", null=True, blank=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "academic_year"
        verbose_name = "学年"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        constraints = [
            # 保证全局只有一个 ACTIVE 学年（部分唯一索引）
            models.UniqueConstraint(
                fields=["status"],
                condition=Q(status=AcademicYearStatus.ACTIVE.value),
                name="uk_status_active",
            ),
        ]

    def __str__(self):
        return self.name
