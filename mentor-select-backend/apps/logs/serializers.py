"""
日志管理序列化器
"""
from rest_framework import serializers

from apps.logs.models import LoginLog, OperationLog


class OperationLogSerializer(serializers.ModelSerializer):
    """操作日志序列化器"""

    action_display = serializers.CharField(
        source="get_action_display", read_only=True
    )

    class Meta:
        model = OperationLog
        fields = (
            "id",
            "academic_year",
            "user",
            "action",
            "action_display",
            "target_type",
            "target_id",
            "detail",
            "ip_address",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class LoginLogSerializer(serializers.ModelSerializer):
    """登录日志序列化器"""

    class Meta:
        model = LoginLog
        fields = (
            "id",
            "user",
            "username",
            "ip_address",
            "user_agent",
            "is_success",
            "fail_reason",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
