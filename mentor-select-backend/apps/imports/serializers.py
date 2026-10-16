"""导入管理序列化器"""
from rest_framework import serializers

from apps.imports.models import ImportLog, ImportTask


class ImportTaskSerializer(serializers.ModelSerializer):
    """导入任务序列化器"""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    triggered_by_name = serializers.CharField(
        source="triggered_by.username", read_only=True
    )

    class Meta:
        model = ImportTask
        fields = (
            "id",
            "academic_year",
            "role",
            "role_display",
            "status",
            "status_display",
            "file_name",
            "file_size",
            "total_rows",
            "success_count",
            "failed_count",
            "error_message",
            "started_at",
            "finished_at",
            "triggered_by",
            "triggered_by_name",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "total_rows",
            "success_count",
            "failed_count",
            "error_message",
            "started_at",
            "finished_at",
            "version",
            "created_at",
            "updated_at",
        )


class ImportLogSerializer(serializers.ModelSerializer):
    """导入日志序列化器"""

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    created_user_name = serializers.CharField(
        source="created_user.username", read_only=True, allow_null=True
    )

    class Meta:
        model = ImportLog
        fields = (
            "id",
            "task",
            "row_number",
            "row_data",
            "status",
            "status_display",
            "error_reason",
            "created_user",
            "created_user_name",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ExcelUploadSerializer(serializers.Serializer):
    """Excel 上传参数校验"""

    file = serializers.FileField(required=True, help_text="Excel 文件(.xlsx)")
    role = serializers.IntegerField(required=True, help_text="角色: 1=学生, 2=导师, 3=管理员")
    academic_year = serializers.IntegerField(required=True, help_text="学年 ID")

    def validate_role(self, value):
        from apps.common.enums import UserRole

        if value not in (
            UserRole.STUDENT.value,
            UserRole.TEACHER.value,
            UserRole.ADMIN.value,
        ):
            raise serializers.ValidationError("角色必须是 1(学生)、2(导师) 或 3(管理员)")
        return value

    def validate_file(self, value):
        """校验文件扩展名和大小"""
        # 文件扩展名
        name = value.name.lower()
        if not name.endswith(".xlsx"):
            raise serializers.ValidationError("仅支持 .xlsx 格式文件")

        # 文件大小
        from apps.imports.excel.constants import MAX_FILE_SIZE

        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"文件大小超过限制 {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
            )
        return value
