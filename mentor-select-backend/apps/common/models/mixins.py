"""
Model Mixins
"""
from django.contrib.auth.models import UserManager
from django.db import models


class SoftDeleteManager(models.Manager):
    """软删除 Manager，默认只返回未删除的记录"""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """包含已删除记录的 Manager"""

    def get_queryset(self):
        return super().get_queryset().all()


class SoftDeleteUserManager(UserManager, SoftDeleteManager):
    """User 模型专用软删除 Manager

    继承 UserManager 以支持 create_user / create_superuser，
    同时叠加 SoftDeleteManager 的软删除过滤。

    重写 _create_user 以适配 User 模型移除 email 字段的情况。
    """

    def _create_user(self, username, email, password, **extra_fields):
        """创建用户（不传递 email 字段，因为 User 模型已移除该字段）"""
        if not username:
            raise ValueError("用户名必须设置")
        # User 模型已移除 email 字段，不传递
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """创建超级用户（不传递 email 字段）"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(username, None, password, **extra_fields)
