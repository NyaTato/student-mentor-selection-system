"""
学生管理业务服务
"""
from __future__ import annotations

from apps.common.error_codes import ErrorCode
from apps.common.exceptions import BusinessException, NotFoundError
from apps.common.logger import get_logger
from apps.common.services import BaseService
from apps.students.models import StudentProfile
from apps.students.repositories import StudentProfileRepository

logger = get_logger("students.services")


class StudentProfileService(BaseService):
    """学生档案业务服务"""

    repository = StudentProfileRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询学生列表"""
        return self.repository.list(
            filters=filters, order_by=order_by or ["-user_id"]
        )

    def get_by_id(self, pk: int) -> StudentProfile:
        return self.repository.get_by_id(pk)

    def get_by_user_id(self, user_id: int) -> StudentProfile:
        """按 user_id 查询学生档案"""
        profile = self.repository.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError(
                f"StudentProfile (user_id={user_id}) 不存在",
            )
        return profile

    def get_by_student_number(self, student_number: str) -> StudentProfile | None:
        """按学号查询"""
        return self.repository.get_by_student_number(student_number)

    def create(self, validated_data: dict) -> StudentProfile:
        """创建学生档案

        - 校验 student_number 唯一
        """
        student_number = validated_data.get("student_number")
        if student_number and self.repository.exists(student_number=student_number):
            raise BusinessException(
                f"学号 {student_number} 已存在",
                code=ErrorCode.STUDENT_NUMBER_EXISTS,
            )
        return self.repository.create(**validated_data)

    def update(self, pk: int, validated_data: dict) -> StudentProfile:
        """更新学生档案"""
        instance = self.repository.get_by_id(pk)

        # 若修改学号，校验唯一性（排除自身）
        new_student_number = validated_data.get("student_number")
        if new_student_number and new_student_number != instance.student_number:
            if self.repository.exists(student_number=new_student_number):
                raise BusinessException(
                    f"学号 {new_student_number} 已存在",
                    code=ErrorCode.STUDENT_NUMBER_EXISTS,
                )

        return self.repository.update(instance, validated_data)

    def delete(self, pk: int) -> StudentProfile:
        """软删除学生档案"""
        instance = self.repository.get_by_id(pk)
        self.repository.soft_delete(instance)
        return instance
