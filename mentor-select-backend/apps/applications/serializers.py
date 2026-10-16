"""
申请管理序列化器
"""
from rest_framework import serializers

from apps.applications.models import Application
from apps.common.enums import ApplicationRound


class ApplicationSerializer(serializers.ModelSerializer):
    """申请序列化器"""

    round_display = serializers.CharField(source="get_round_display", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    student_name = serializers.CharField(source="student.name", read_only=True)
    student_number = serializers.CharField(
        source="student.student_number", read_only=True
    )
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    teacher_number = serializers.CharField(
        source="teacher.teacher_number", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "student",
            "student_name",
            "student_number",
            "teacher",
            "teacher_name",
            "teacher_number",
            "round",
            "round_display",
            "status",
            "status_display",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "version",
            "created_at",
            "updated_at",
            "round_display",
            "status_display",
            "student_name",
            "student_number",
            "teacher_name",
            "teacher_number",
            "academic_year_name",
        )


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """学生提交申请序列化器"""

    class Meta:
        model = Application
        fields = (
            "academic_year",
            "teacher",
            "round",
        )

    def validate_round(self, value):
        if value not in [choice.value for choice in ApplicationRound]:
            raise serializers.ValidationError("非法轮次")
        return value


class ApplicationBatchActionSerializer(serializers.Serializer):
    """批量审核序列化器"""

    application_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=True,
        min_length=1,
    )
