"""
基础 Model
所有 Model 的抽象基类
"""
from django.db import models


class TimeStampedModel(models.Model):
    """提供 created_at 和 updated_at 字段"""

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """所有业务 Model 的基类，包含软删除和乐观锁"""

    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    version = models.PositiveIntegerField("乐观锁版本", default=1)

    class Meta:
        abstract = True
