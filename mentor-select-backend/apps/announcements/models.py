"""
公告管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.models import BaseModel
from apps.common.models.mixins import AllObjectsManager, SoftDeleteManager


class Announcement(BaseModel):
    """系统公告 - 按学年隔离，学生仅可见当前 ACTIVE 学年的公告"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="announcements",
        verbose_name="所属学年",
    )
    title = models.CharField("标题", max_length=100)
    content = models.TextField("内容")
    is_published = models.BooleanField("是否已发布", default=False)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        db_column="created_by",
        related_name="announcements",
        verbose_name="创建人",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "announcement"
        verbose_name = "公告"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["academic_year", "is_published", "published_at"],
                name="idx_year_published",
            ),
        ]

    def __str__(self):
        return self.title
