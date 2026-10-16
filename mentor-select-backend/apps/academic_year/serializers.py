"""
学年管理序列化器
"""
from rest_framework import serializers

from apps.academic_year.models import AcademicYear
from apps.common.validators import validate_academic_year_name


class AcademicYearSerializer(serializers.ModelSerializer):
    """学年序列化器"""

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = AcademicYear
        fields = (
            "id",
            "name",
            "start_year",
            "end_year",
            "status",
            "status_display",
            "activated_at",
            "closed_at",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = (
            "id",
            "status",
            "activated_at",
            "closed_at",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )

    def validate_name(self, value):
        validate_academic_year_name(value)
        return value

    def validate(self, attrs):
        """校验 start_year < end_year"""
        start_year = attrs.get("start_year")
        end_year = attrs.get("end_year")
        if start_year is not None and end_year is not None:
            if start_year >= end_year:
                raise serializers.ValidationError("开始年份必须小于结束年份")
        return attrs


class AcademicYearUpdateSerializer(AcademicYearSerializer):
    """学年更新序列化器（不允许修改 status）"""

    class Meta(AcademicYearSerializer.Meta):
        read_only_fields = (
            "id",
            "status",
            "activated_at",
            "closed_at",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
