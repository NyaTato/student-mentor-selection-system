"""
分配结果序列化器
"""
from rest_framework import serializers

from apps.assignments.models import Admission, AutoAssignmentLog


class AdmissionSerializer(serializers.ModelSerializer):
    """录取结果序列化器"""

    source_display = serializers.CharField(source="get_source_display", read_only=True)
    student_name = serializers.CharField(source="student.name", read_only=True)
    student_number = serializers.CharField(source="student.student_number", read_only=True)
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    teacher_number = serializers.CharField(source="teacher.teacher_number", read_only=True)

    class Meta:
        model = Admission
        fields = (
            "id",
            "academic_year",
            "student",
            "student_name",
            "student_number",
            "teacher",
            "teacher_name",
            "teacher_number",
            "source",
            "source_display",
            "application",
            "auto_assignment_log",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class AutoAssignmentLogSerializer(serializers.ModelSerializer):
    """自动分配日志序列化器"""

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    triggered_by_name = serializers.CharField(
        source="triggered_by.username", read_only=True
    )
    revoked_by_name = serializers.CharField(
        source="revoked_by.username", read_only=True
    )

    class Meta:
        model = AutoAssignmentLog
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "status",
            "status_display",
            "total_unassigned",
            "assigned_count",
            "failed_count",
            "triggered_by",
            "triggered_by_name",
            "started_at",
            "finished_at",
            "is_revoked",
            "revoked_at",
            "revoked_by",
            "revoked_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


# ===== 自动分配请求/响应序列化器 =====


class AutoAssignmentPreviewRequestSerializer(serializers.Serializer):
    """自动分配预览请求"""

    academic_year = serializers.IntegerField(required=True, help_text="学年 ID")


class AutoAssignmentRunRequestSerializer(serializers.Serializer):
    """自动分配执行请求"""

    academic_year = serializers.IntegerField(required=True, help_text="学年 ID")
    dry_run = serializers.BooleanField(
        required=False, default=False, help_text="是否仅预览（不实际创建 admission）"
    )


class AutoAssignmentRevokeRequestSerializer(serializers.Serializer):
    """自动分配撤销请求"""

    auto_assignment_log = serializers.IntegerField(
        required=True, help_text="自动分配日志 ID"
    )
    academic_year = serializers.IntegerField(required=True, help_text="学年 ID")


class ManualAssignRequestSerializer(serializers.Serializer):
    """管理员人工分配请求

    POST /api/v2/assignments/manual-assign/
    Body: {"academic_year": int, "student": int, "teacher": int}
    """

    academic_year = serializers.IntegerField(
        required=True, min_value=1, help_text="学年 ID"
    )
    student = serializers.IntegerField(
        required=True, min_value=1, help_text="学生 user_id（= StudentProfile 主键）"
    )
    teacher = serializers.IntegerField(
        required=True, min_value=1, help_text="导师 user_id（= TeacherProfile 主键）"
    )


class AssignmentPreviewItemSerializer(serializers.Serializer):
    """单个分配预览项"""

    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    student_number = serializers.CharField()
    teacher_id = serializers.IntegerField()
    teacher_name = serializers.CharField()
    teacher_number = serializers.CharField()
    remaining_quota = serializers.IntegerField()


class AutoAssignmentPreviewResponseSerializer(serializers.Serializer):
    """自动分配预览响应"""

    total_unassigned = serializers.IntegerField()
    available_teachers = serializers.IntegerField()
    total_remaining_quota = serializers.IntegerField()
    previews = AssignmentPreviewItemSerializer(many=True)


class AutoAssignmentRunResponseSerializer(serializers.Serializer):
    """自动分配执行响应"""

    log_id = serializers.IntegerField(allow_null=True)
    total_unassigned = serializers.IntegerField()
    assigned_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    is_dry_run = serializers.BooleanField()
    is_all_assigned = serializers.BooleanField()
    previews = AssignmentPreviewItemSerializer(many=True)


class AutoAssignmentRevokeResponseSerializer(serializers.Serializer):
    """自动分配撤销响应"""

    revoked_count = serializers.IntegerField()
    log_id = serializers.IntegerField()
