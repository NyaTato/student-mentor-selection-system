"""
导师管理序列化器
"""
from rest_framework import serializers

from apps.common.validators import (
    validate_chinese_name,
    validate_quota,
    validate_research_area,
    validate_teacher_number,
)
from apps.teachers.models import TeacherProfile, TeacherQuota


class TeacherProfileSerializer(serializers.ModelSerializer):
    """导师档案序列化器"""

    username = serializers.CharField(source="user.username", read_only=True)
    role_display = serializers.CharField(source="user.get_role_display", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = (
            "user",
            "teacher_number",
            "name",
            "college",
            "title",
            "research_area",
            "profile",
            "graduation_direction",
            "thesis_topic",
            "student_requirement",
            "username",
            "role_display",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = (
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
            "username",
            "role_display",
        )

    def validate_teacher_number(self, value):
        validate_teacher_number(value)
        return value

    def validate_name(self, value):
        validate_chinese_name(value)
        return value

    def validate_research_area(self, value):
        validate_research_area(value)
        return value


class TeacherProfileCreateSerializer(serializers.ModelSerializer):
    """导师档案创建序列化器（管理端使用）"""

    class Meta:
        model = TeacherProfile
        fields = (
            "user",
            "teacher_number",
            "name",
            "college",
            "title",
            "research_area",
            "profile",
            "graduation_direction",
            "thesis_topic",
            "student_requirement",
        )

    def validate_teacher_number(self, value):
        validate_teacher_number(value)
        return value

    def validate_name(self, value):
        validate_chinese_name(value)
        return value


class TeacherProfileUpdateSerializer(serializers.ModelSerializer):
    """导师档案更新序列化器（导师可更新自己的研究方向等）"""

    class Meta:
        model = TeacherProfile
        fields = (
            "college",
            "title",
            "research_area",
            "profile",
            "graduation_direction",
            "thesis_topic",
            "student_requirement",
        )

    def validate_research_area(self, value):
        validate_research_area(value)
        return value


class TeacherQuotaSerializer(serializers.ModelSerializer):
    """导师名额序列化器"""

    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    teacher_number = serializers.CharField(
        source="teacher.teacher_number", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    class Meta:
        model = TeacherQuota
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "teacher",
            "teacher_name",
            "teacher_number",
            "max_quota",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = (
            "id",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
            "teacher_name",
            "teacher_number",
            "academic_year_name",
        )

    def validate_max_quota(self, value):
        validate_quota(value)
        return value


class TeacherQuotaBatchSerializer(serializers.Serializer):
    """批量设置名额序列化器"""

    academic_year = serializers.IntegerField(required=True)
    quotas = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        min_length=1,
    )

    def validate_quotas(self, value):
        for item in value:
            if "teacher_id" not in item:
                raise serializers.ValidationError("每条记录必须包含 teacher_id")
            if "max_quota" not in item:
                raise serializers.ValidationError("每条记录必须包含 max_quota")
            try:
                max_quota = int(item["max_quota"])
            except (TypeError, ValueError):
                raise serializers.ValidationError("max_quota 必须为整数")
            if max_quota < 0 or max_quota > 99:
                raise serializers.ValidationError("max_quota 必须在 0-99 之间")
        return value
