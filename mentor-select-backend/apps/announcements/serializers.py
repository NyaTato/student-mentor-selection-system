"""
公告管理序列化器
"""
from rest_framework import serializers

from apps.announcements.models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    """公告序列化器"""

    class Meta:
        model = Announcement
        fields = (
            "id",
            "academic_year",
            "title",
            "content",
            "is_published",
            "published_at",
            "created_by",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = (
            "id",
            "published_at",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("标题不能为空")
        if len(value) > 100:
            raise serializers.ValidationError("标题不能超过 100 个字符")
        return value

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("内容不能为空")
        return value


class AnnouncementCreateSerializer(AnnouncementSerializer):
    """公告创建序列化器

    created_by 由 View 自动填充为当前登录用户。
    """

    class Meta(AnnouncementSerializer.Meta):
        read_only_fields = (
            "id",
            "published_at",
            "created_by",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )


class AnnouncementUpdateSerializer(AnnouncementSerializer):
    """公告更新序列化器（不允许修改 created_by / academic_year）"""

    class Meta(AnnouncementSerializer.Meta):
        read_only_fields = (
            "id",
            "academic_year",
            "created_by",
            "published_at",
            "version",
            "created_at",
            "updated_at",
            "deleted_at",
        )
