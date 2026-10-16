"""
日志管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.enums import OperationAction


class OperationLog(models.Model):
    """操作日志 - 只写不改，无软删除，无乐观锁"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.CASCADE,
        db_column="academic_year_id",
        related_name="operation_logs",
        null=True,
        blank=True,
        verbose_name="所属学年",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        db_column="user_id",
        related_name="operation_logs",
        null=True,
        blank=True,
        verbose_name="操作人",
    )
    action = models.PositiveSmallIntegerField(
        "操作类型", choices=OperationAction.choices
    )
    target_type = models.CharField("操作对象类型", max_length=32)
    target_id = models.BigIntegerField("操作对象ID")
    detail = models.TextField("操作详情", null=True, blank=True)
    ip_address = models.GenericIPAddressField("操作IP")
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        db_table = "operation_log"
        verbose_name = "操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="idx_oplog_user_created",
            ),
            models.Index(
                fields=["academic_year", "created_at"],
                name="idx_oplog_year_created",
            ),
            models.Index(
                fields=["target_type", "target_id"],
                name="idx_target",
            ),
            models.Index(fields=["created_at"], name="idx_oplog_created_at"),
        ]

    def __str__(self):
        return f"{self.user_id} {self.get_action_display()} {self.target_type}:{self.target_id}"


class LoginLog(models.Model):
    """登录日志 - 只写不改，无软删除，无乐观锁"""

    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        db_column="user_id",
        related_name="login_logs",
        null=True,
        blank=True,
        verbose_name="登录用户",
    )
    username = models.CharField("用户名", max_length=64)
    ip_address = models.GenericIPAddressField("登录IP")
    user_agent = models.CharField(
        "浏览器标识", max_length=512, null=True, blank=True
    )
    is_success = models.BooleanField("是否成功")
    fail_reason = models.CharField(
        "失败原因", max_length=128, null=True, blank=True
    )
    created_at = models.DateTimeField("登录时间", auto_now_add=True)

    class Meta:
        db_table = "login_log"
        verbose_name = "登录日志"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="idx_loginlog_user_created",
            ),
            models.Index(fields=["created_at"], name="idx_loginlog_created_at"),
        ]

    def __str__(self):
        return f"{self.username} @ {self.created_at}"
