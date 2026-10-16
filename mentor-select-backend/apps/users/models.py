"""
用户管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.enums import UserRole, UserStatus
from apps.common.models import BaseModel
from apps.common.models.mixins import (
    AllObjectsManager,
    SoftDeleteManager,
    SoftDeleteUserManager,
)


class User(AbstractUser):
    """用户模型 - 认证与身份"""

    username = models.CharField("用户名", max_length=64, unique=True)
    password = models.CharField("密码", max_length=128)
    role = models.PositiveSmallIntegerField(
        "角色", choices=UserRole.choices, default=UserRole.STUDENT
    )
    status = models.PositiveSmallIntegerField(
        "状态", choices=UserStatus.choices, default=UserStatus.ACTIVE
    )
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    version = models.PositiveIntegerField("乐观锁版本", default=1)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    # 移除 AbstractUser 中 DATABASE.md 未定义的字段
    first_name = None
    last_name = None
    email = None

    objects = SoftDeleteUserManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name
        ordering = ["-id"]

    def __str__(self):
        return self.username


class AdminProfile(BaseModel):
    """管理员档案 - 与 User 一对一，共享主键"""

    user = models.OneToOneField(
        "users.User",
        on_delete=models.PROTECT,
        primary_key=True,
        db_column="user_id",
        related_name="admin_profile",
        verbose_name="用户",
    )
    name = models.CharField("姓名", max_length=64)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "admin_profile"
        verbose_name = "管理员档案"
        verbose_name_plural = verbose_name
        ordering = ["-user_id"]

    def __str__(self):
        return self.name
