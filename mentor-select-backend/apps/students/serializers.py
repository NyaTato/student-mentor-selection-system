"""
学生管理序列化器
"""
from rest_framework import serializers

from apps.common.validators import validate_chinese_name, validate_student_number
from apps.students.models import StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    """学生档案序列化器"""

    username = serializers.CharField(source="user.username", read_only=True)
    role_display = serializers.CharField(source="user.get_role_display", read_only=True)

    class Meta:
        model = StudentProfile
        fields = (
            "user",
            "student_number",
            "name",
            "major",
            "class_name",
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

    def validate_student_number(self, value):
        validate_student_number(value)
        return value

    def validate_name(self, value):
        validate_chinese_name(value)
        return value


class StudentProfileCreateSerializer(serializers.ModelSerializer):
    """学生档案创建序列化器（管理端使用）"""

    class Meta:
        model = StudentProfile
        fields = (
            "user",
            "student_number",
            "name",
            "major",
            "class_name",
        )

    def validate_student_number(self, value):
        validate_student_number(value)
        return value

    def validate_name(self, value):
        validate_chinese_name(value)
        return value


class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    """学生档案更新序列化器"""

    class Meta:
        model = StudentProfile
        fields = (
            "student_number",
            "name",
            "major",
            "class_name",
        )

    def validate_student_number(self, value):
        validate_student_number(value)
        return value

    def validate_name(self, value):
        validate_chinese_name(value)
        return value
