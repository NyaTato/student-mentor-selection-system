"""
公告管理业务服务

业务规则依据 PROJECT.md：
- 公告按学年隔离
- 学生仅可见当前 ACTIVE 学年已发布的公告
- 管理员可创建/更新/发布/取消发布/删除公告
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.announcements.repositories import AnnouncementRepository
from apps.common.exceptions import BusinessException
from apps.common.logger import get_logger
from apps.common.services import BaseService
from apps.monitoring.services import MetricsService

logger = get_logger("announcements.services")


class AnnouncementService(BaseService):
    """公告业务服务"""

    repository = AnnouncementRepository()

    # ===== 查询 =====

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询公告列表，默认按 ID 倒序"""
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> Announcement:
        return self.repository.get_by_id(pk)

    def list_by_academic_year(
        self, academic_year_id: int, only_published: bool = False
    ):
        """按学年查询公告"""
        return self.repository.list_by_academic_year(
            academic_year_id, only_published
        )

    # ===== 创建 =====

    @transaction.atomic
    def create(self, validated_data: dict) -> Announcement:
        """创建公告

        - 自动填充 created_by 为当前操作用户
        - 若 is_published=True，自动填充 published_at
        """
        created_by = validated_data.get("created_by")
        is_published = validated_data.get("is_published", False)

        if is_published and "published_at" not in validated_data:
            validated_data["published_at"] = timezone.now()

        instance = self.repository.create(**validated_data)
        logger.info(
            "Announcement created: id=%s, title=%s, by=%s",
            instance.id, instance.title,
            created_by.id if created_by else None,
        )
        MetricsService.record_announcement("create")
        return instance

    # ===== 更新 =====

    @transaction.atomic
    def update(self, pk: int, validated_data: dict) -> Announcement:
        """更新公告"""
        instance = self.repository.get_by_id(pk)
        instance = self.repository.update(instance, validated_data)
        MetricsService.record_announcement("update")
        return instance

    # ===== 删除 =====

    @transaction.atomic
    def delete(self, pk: int) -> Announcement:
        """软删除公告"""
        instance = self.repository.get_by_id(pk)
        self.repository.soft_delete(instance)
        logger.info("Announcement soft deleted: id=%s", pk)
        MetricsService.record_announcement("delete")
        return instance

    # ===== 发布/取消发布 =====

    @transaction.atomic
    def publish(self, pk: int) -> Announcement:
        """发布公告

        - 设置 is_published=True
        - 自动填充 published_at
        """
        instance = self.repository.get_by_id(pk)
        if instance.is_published:
            raise BusinessException("该公告已发布")

        instance.is_published = True
        instance.published_at = timezone.now()
        instance.version = (instance.version or 0) + 1
        instance.save(update_fields=[
            "is_published", "published_at", "version", "updated_at",
        ])

        logger.info("Announcement published: id=%s", instance.id)
        MetricsService.record_announcement("publish")
        return instance

    @transaction.atomic
    def unpublish(self, pk: int) -> Announcement:
        """取消发布公告

        - 设置 is_published=False
        - 保留 published_at 作为历史记录
        """
        instance = self.repository.get_by_id(pk)
        if not instance.is_published:
            raise BusinessException("该公告未发布")

        instance.is_published = False
        instance.version = (instance.version or 0) + 1
        instance.save(update_fields=["is_published", "version", "updated_at"])

        logger.info("Announcement unpublished: id=%s", instance.id)
        MetricsService.record_announcement("unpublish")
        return instance
