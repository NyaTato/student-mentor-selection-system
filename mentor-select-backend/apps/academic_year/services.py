"""
学年管理业务服务

业务规则依据 PROJECT.md：
- 全局只能有一个 ACTIVE 学年（DB 部分唯一索引 uk_status_active）
- 激活新学年前，需将当前 ACTIVE 学年归档
- 学年关闭后进入 ARCHIVED 状态
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.academic_year.models import AcademicYear
from apps.academic_year.repositories import AcademicYearRepository
from apps.common.enums import AcademicYearStatus
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import (
    BusinessException,
    NotFoundError,
    ValidationError,
)
from apps.common.logger import get_logger
from apps.common.services import BaseService
from apps.monitoring.services import MetricsService

logger = get_logger("academic_year.services")


class AcademicYearService(BaseService):
    """学年业务服务"""

    repository = AcademicYearRepository()

    # ===== 查询 =====

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询学年列表，默认按 ID 倒序"""
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> AcademicYear:
        return self.repository.get_by_id(pk)

    def get_active(self) -> AcademicYear | None:
        """查询当前激活的学年"""
        return self.repository.get_active()

    # ===== 创建 =====

    @transaction.atomic
    def create(self, validated_data: dict) -> AcademicYear:
        """创建学年

        - 校验 name 唯一
        - 校验 start_year < end_year
        """
        name = validated_data.get("name")
        if name and self.repository.exists(name=name):
            raise BusinessException(
                f"学年名称 {name} 已存在",
                code=ErrorCode.ACADEMIC_YEAR_EXISTS,
            )

        start_year = validated_data.get("start_year")
        end_year = validated_data.get("end_year")
        if start_year is not None and end_year is not None:
            if start_year >= end_year:
                raise ValidationError("开始年份必须小于结束年份")

        instance = self.repository.create(**validated_data)
        logger.info("AcademicYear created: id=%s, name=%s", instance.id, instance.name)
        MetricsService.record_academic_year("create")
        return instance

    # ===== 更新 =====

    @transaction.atomic
    def update(self, pk: int, validated_data: dict) -> AcademicYear:
        """更新学年

        - 若修改 name，校验唯一性（排除自身）
        - 若修改 start_year/end_year，校验 start_year < end_year
        - 不允许直接修改 status（通过 activate/close 操作）
        """
        instance = self.repository.get_by_id(pk)

        new_name = validated_data.get("name")
        if new_name and new_name != instance.name:
            if self.repository.exists(name=new_name):
                raise BusinessException(
                    f"学年名称 {new_name} 已存在",
                    code=ErrorCode.ACADEMIC_YEAR_EXISTS,
                )

        # 禁止通过 update 直接修改 status
        if "status" in validated_data:
            raise ValidationError("不允许直接修改状态，请使用 activate/close 操作")

        start_year = validated_data.get("start_year", instance.start_year)
        end_year = validated_data.get("end_year", instance.end_year)
        if start_year >= end_year:
            raise ValidationError("开始年份必须小于结束年份")

        return self.repository.update(instance, validated_data)

    # ===== 删除 =====

    @transaction.atomic
    def delete(self, pk: int) -> AcademicYear:
        """软删除学年

        - ACTIVE 学年不允许删除
        """
        instance = self.repository.get_by_id(pk)
        if instance.status == AcademicYearStatus.ACTIVE.value:
            raise BusinessException(
                "激活中的学年不允许删除，请先关闭",
                code=ErrorCode.ACADEMIC_YEAR_INACTIVE,
            )
        self.repository.soft_delete(instance)
        logger.info("AcademicYear soft deleted: id=%s", pk)
        return instance

    # ===== 激活 =====

    @transaction.atomic
    def activate(self, pk: int) -> AcademicYear:
        """激活学年

        业务规则：
        - 若当前已有 ACTIVE 学年，先将其归档
        - 将目标学年状态置为 ACTIVE
        - 记录激活时间
        - 自动初始化系统状态（INIT）和调度配置（通过 SystemStateService 委托）
        """
        instance = self.repository.get_by_id(pk)

        if instance.status == AcademicYearStatus.ACTIVE.value:
            raise BusinessException("该学年已是激活状态")

        if instance.status == AcademicYearStatus.ARCHIVED.value:
            raise BusinessException(
                "已归档的学年不能重新激活",
                code=ErrorCode.ACADEMIC_YEAR_ARCHIVED,
            )

        # 归档当前激活的学年（通过 Repository）
        current_active = self.repository.get_active()
        if current_active is not None and current_active.id != instance.id:
            self.repository.update(current_active, {
                "status": AcademicYearStatus.ARCHIVED.value,
                "closed_at": timezone.now(),
            })
            logger.info("Previous active year archived: id=%s", current_active.id)

        # 激活目标学年（通过 Repository）
        instance = self.repository.update(instance, {
            "status": AcademicYearStatus.ACTIVE.value,
            "activated_at": timezone.now(),
        })

        # 自动初始化系统状态和调度配置（跨聚合委托，避免直接操作 system.models）
        from apps.system.services import (
            SystemStateScheduleService,
            SystemStateService,
        )

        SystemStateService().init_for_academic_year(instance.id)
        SystemStateScheduleService().init_for_academic_year(instance.id)

        logger.info("AcademicYear activated: id=%s", instance.id)
        MetricsService.record_academic_year("activate")
        return instance

    # ===== 关闭 =====

    @transaction.atomic
    def close(self, pk: int) -> AcademicYear:
        """关闭学年（归档）

        业务规则：
        - 仅 ACTIVE 学年可关闭
        - 关闭后状态变为 ARCHIVED
        - 记录关闭时间
        """
        instance = self.repository.get_by_id(pk)

        if instance.status != AcademicYearStatus.ACTIVE.value:
            raise BusinessException("仅激活中的学年可关闭")

        instance = self.repository.update(instance, {
            "status": AcademicYearStatus.ARCHIVED.value,
            "closed_at": timezone.now(),
        })

        logger.info("AcademicYear closed: id=%s", instance.id)
        MetricsService.record_academic_year("close")
        return instance
