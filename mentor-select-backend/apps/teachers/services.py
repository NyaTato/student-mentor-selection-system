"""
导师管理业务服务
"""
from __future__ import annotations

from django.db import transaction

from apps.academic_year.repositories import AcademicYearRepository
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import BusinessException, NotFoundError
from apps.common.logger import get_logger
from apps.common.services import BaseService
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.teachers.repositories import TeacherProfileRepository, TeacherQuotaRepository

logger = get_logger("teachers.services")


class TeacherProfileService(BaseService):
    """导师档案业务服务"""

    repository = TeacherProfileRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        return self.repository.list(filters=filters, order_by=order_by or ["-user_id"])

    def get_by_id(self, pk: int) -> TeacherProfile:
        return self.repository.get_by_id(pk)

    def get_by_user_id(self, user_id: int) -> TeacherProfile:
        profile = self.repository.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError(
                f"TeacherProfile (user_id={user_id}) 不存在",
            )
        return profile

    def get_by_teacher_number(self, teacher_number: str) -> TeacherProfile | None:
        return self.repository.get_by_teacher_number(teacher_number)

    def create(self, validated_data: dict) -> TeacherProfile:
        """创建导师档案

        - 校验 teacher_number 唯一
        """
        teacher_number = validated_data.get("teacher_number")
        if teacher_number and self.repository.exists(teacher_number=teacher_number):
            raise BusinessException(
                f"工号 {teacher_number} 已存在",
                code=ErrorCode.TEACHER_NUMBER_EXISTS,
            )
        return self.repository.create(**validated_data)

    def update(self, pk: int, validated_data: dict) -> TeacherProfile:
        """更新导师档案"""
        instance = self.repository.get_by_id(pk)

        new_teacher_number = validated_data.get("teacher_number")
        if new_teacher_number and new_teacher_number != instance.teacher_number:
            if self.repository.exists(teacher_number=new_teacher_number):
                raise BusinessException(
                    f"工号 {new_teacher_number} 已存在",
                    code=ErrorCode.TEACHER_NUMBER_EXISTS,
                )

        return self.repository.update(instance, validated_data)

    def delete(self, pk: int) -> TeacherProfile:
        """软删除导师档案"""
        instance = self.repository.get_by_id(pk)
        self.repository.soft_delete(instance)
        return instance


class TeacherQuotaService(BaseService):
    """导师名额业务服务"""

    repository = TeacherQuotaRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> TeacherQuota:
        return self.repository.get_by_id(pk)

    def get_by_year_and_teacher(
        self, academic_year_id: int, teacher_id: int
    ) -> TeacherQuota:
        """按学年+导师查询名额"""
        quota = self.repository.get_by_year_and_teacher(academic_year_id, teacher_id)
        if quota is None:
            raise NotFoundError(
                f"TeacherQuota (year={academic_year_id}, teacher={teacher_id}) 不存在",
            )
        return quota

    def list_by_year(self, academic_year_id: int):
        """按学年查询所有名额"""
        return self.repository.list_by_year(academic_year_id)

    def list_by_teacher(self, teacher_id: int):
        """按导师查询所有学年的名额"""
        return self.repository.list_by_teacher(teacher_id)

    @staticmethod
    def _assert_quota_not_below_admitted(
        academic_year_id: int, teacher_id: int, max_quota: int
    ) -> int:
        """名额不得低于已录取人数（同一事务 + 当前读）

        使用 AdmissionRepository 的**当前读**计数（select_for_update 物化），
        与录取路径共用同一计数语义，避免 MySQL REPEATABLE READ 下
        读到过期快照而把名额改到低于已录取人数。

        Returns:
            当前已录取人数
        """
        from apps.assignments.repositories import AdmissionRepository

        admitted = AdmissionRepository().count_by_teacher_current(
            teacher_id, academic_year_id
        )
        if max_quota < admitted:
            raise BusinessException(
                f"名额不能低于已录取人数（当前已录取 {admitted} 人）",
                code=ErrorCode.QUOTA_INVALID,
            )
        return admitted

    @transaction.atomic
    def create(self, validated_data: dict) -> TeacherQuota:
        """创建导师名额

        - 校验同一学年+导师的组合唯一（数据库约束 uk_year_teacher）
        - 校验名额不低于已录取人数（同一事务 + 当前读）
        """
        academic_year_id = validated_data.get("academic_year_id")
        teacher_id = validated_data.get("teacher_id")

        # 注意：validated_data 中如果是 FK 字段，会是 ORM 对象
        if hasattr(academic_year_id, "id"):
            academic_year_id = academic_year_id.id
        if hasattr(teacher_id, "id"):
            teacher_id = teacher_id.id

        if academic_year_id and teacher_id:
            if self.repository.exists(
                academic_year_id=academic_year_id, teacher_id=teacher_id
            ):
                raise BusinessException(
                    f"该导师在学年 {academic_year_id} 中已有名额记录",
                    code=ErrorCode.DUPLICATE,
                )

        # 校验名额上限
        max_quota = validated_data.get("max_quota", 0)
        if max_quota < 0 or max_quota > 99:
            raise BusinessException(
                "名额必须在 0-99 之间",
                code=ErrorCode.QUOTA_INVALID,
            )

        if academic_year_id and teacher_id:
            self._assert_quota_not_below_admitted(
                academic_year_id, teacher_id, max_quota
            )

        return self.repository.create(**validated_data)

    @transaction.atomic
    def update(self, pk: int, validated_data: dict) -> TeacherQuota:
        """更新导师名额

        - 校验名额上限范围
        - 锁定名额行后校验「名额 >= 已录取人数」（当前读计数）
        """
        instance = self.repository.get_by_id(pk)

        # 校验名额上限
        max_quota = validated_data.get("max_quota")
        if max_quota is not None and (max_quota < 0 or max_quota > 99):
            raise BusinessException(
                "名额必须在 0-99 之间",
                code=ErrorCode.QUOTA_INVALID,
            )

        # 固定锁顺序第 2 步：锁 quota 行（第 3 步的当前读计数在 helper 内）
        self.repository.get_for_update_by_year_and_teacher(
            instance.academic_year_id, instance.teacher_id
        )

        effective_quota = max_quota if max_quota is not None else instance.max_quota
        self._assert_quota_not_below_admitted(
            instance.academic_year_id, instance.teacher_id, effective_quota
        )

        return self.repository.update(instance, validated_data)

    @transaction.atomic
    def delete(self, pk: int) -> TeacherQuota:
        """软删除导师名额

        删除等价于把名额降为 0；若该导师已有录取记录则拒绝，
        避免出现「已录取人数 > 名额（配置不存在）」的不可解释状态。
        """
        instance = self.repository.get_by_id(pk)

        self.repository.get_for_update_by_year_and_teacher(
            instance.academic_year_id, instance.teacher_id
        )
        self._assert_quota_not_below_admitted(
            instance.academic_year_id, instance.teacher_id, 0
        )

        self.repository.soft_delete(instance)
        return instance

    @transaction.atomic
    def batch_set_quota(
        self, academic_year_id: int, quotas: list[dict]
    ) -> list[TeacherQuota]:
        """批量设置学年下导师名额

        每一项都在同一事务内：锁名额行 -> 当前读已录取数 -> 校验
        「名额 >= 已录取人数」后再写入。

        Args:
            academic_year_id: 学年 ID
            quotas: [{"teacher_id": 1, "max_quota": 5}, ...]
        """
        result = []
        for item in quotas:
            teacher_id = item.get("teacher_id")
            max_quota = item.get("max_quota", 0)

            if max_quota < 0 or max_quota > 99:
                raise BusinessException(
                    "名额必须在 0-99 之间",
                    code=ErrorCode.QUOTA_INVALID,
                )

            existing = self.repository.get_by_year_and_teacher(
                academic_year_id, teacher_id
            )
            # 锁名额行（存在时），保证与录取路径互斥
            self.repository.get_for_update_by_year_and_teacher(
                academic_year_id, teacher_id
            )
            self._assert_quota_not_below_admitted(
                academic_year_id, teacher_id, max_quota
            )

            if existing:
                # 已有记录，更新
                existing = self.repository.update(existing, {"max_quota": max_quota})
                result.append(existing)
            else:
                # 创建新记录（通过 Repository 访问，保持 Service → Repository → Model 分层）
                year = AcademicYearRepository().get_by_id(academic_year_id)
                # TeacherProfile 以 user_id 为主键，无 id 字段
                teacher = TeacherProfileRepository().get_by_filters(user_id=teacher_id)
                instance = self.repository.create(
                    academic_year=year,
                    teacher=teacher,
                    max_quota=max_quota,
                )
                result.append(instance)

        return result
