"""Excel 行数据校验器

对解析后的每行数据进行字段级校验。

校验规则：
- 必填字段非空
- 字段长度限制
- 字段格式（学号、工号、姓名）
- 角色-specific 校验（如学生学号与用户名一致）
"""
from __future__ import annotations

import re
from typing import Any

from apps.common.enums import UserRole
from apps.imports.excel.constants import get_columns


class RowValidator:
    """行数据校验器"""

    # 学号格式：6-12 位数字
    STUDENT_NUMBER_PATTERN = re.compile(r"^\d{6,12}$")
    # 工号格式：4-10 位字母或数字（支持 T0001 格式）
    TEACHER_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9]{4,10}$")
    # 姓名格式：2-64 位中英文
    NAME_PATTERN = re.compile(r"^[\u4e00-\u9fa5A-Za-z·.\s]{2,64}$")

    @classmethod
    def validate(cls, row_data: dict[str, Any], role: int) -> list[str]:
        """校验单行数据

        Args:
            row_data: 行数据字典
            role: UserRole 枚举值

        Returns:
            错误信息列表，空列表表示校验通过
        """
        errors: list[str] = []
        columns = get_columns(role)

        # 1. 必填字段校验 + 长度校验
        for field_name, header, required, max_length, note in columns:
            value = row_data.get(field_name)

            if required and (value is None or str(value).strip() == ""):
                errors.append(f"{header}不能为空")
                continue

            if value is not None and str(value).strip():
                if len(str(value)) > max_length:
                    errors.append(f"{header}长度不能超过 {max_length} 个字符")

        # 2. 角色-specific 格式校验
        if role == UserRole.STUDENT.value:
            errors.extend(cls._validate_student(row_data))
        elif role == UserRole.TEACHER.value:
            errors.extend(cls._validate_teacher(row_data))
        elif role == UserRole.ADMIN.value:
            errors.extend(cls._validate_admin(row_data))

        return errors

    @classmethod
    def _validate_student(cls, row_data: dict[str, Any]) -> list[str]:
        """学生行校验"""
        errors: list[str] = []

        username = row_data.get("username")
        student_number = row_data.get("student_number")
        name = row_data.get("name")

        # 学号格式
        if username and not cls.STUDENT_NUMBER_PATTERN.match(username):
            errors.append("用户名(学号)必须是 6-12 位数字")

        if student_number and not cls.STUDENT_NUMBER_PATTERN.match(student_number):
            errors.append("学号必须是 6-12 位数字")

        # 学号与用户名一致
        if username and student_number and username != student_number:
            errors.append("学号必须与用户名一致")

        # 姓名格式
        if name and not cls.NAME_PATTERN.match(name):
            errors.append("姓名必须是 2-64 位中英文")

        return errors

    @classmethod
    def _validate_teacher(cls, row_data: dict[str, Any]) -> list[str]:
        """导师行校验"""
        errors: list[str] = []

        username = row_data.get("username")
        teacher_number = row_data.get("teacher_number")
        name = row_data.get("name")

        # 工号格式
        if username and not cls.TEACHER_NUMBER_PATTERN.match(username):
            errors.append("用户名(工号)必须是 4-10 位字母或数字")

        if teacher_number and not cls.TEACHER_NUMBER_PATTERN.match(teacher_number):
            errors.append("工号必须是 4-10 位字母或数字")

        # 工号与用户名一致
        if username and teacher_number and username != teacher_number:
            errors.append("工号必须与用户名一致")

        # 姓名格式
        if name and not cls.NAME_PATTERN.match(name):
            errors.append("姓名必须是 2-64 位中英文")

        return errors

    @classmethod
    def _validate_admin(cls, row_data: dict[str, Any]) -> list[str]:
        """管理员行校验"""
        errors: list[str] = []

        username = row_data.get("username")
        name = row_data.get("name")

        # 用户名必填且长度校验已在通用逻辑中处理
        if username and len(username) < 3:
            errors.append("用户名长度不能少于 3 个字符")

        # 姓名格式
        if name and not cls.NAME_PATTERN.match(name):
            errors.append("姓名必须是 2-64 位中英文")

        return errors
