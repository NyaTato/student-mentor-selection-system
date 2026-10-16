"""Teacher Service - 导师业务逻辑层（canonical 实现）

唯一数据源：
- `apps.users.User`（账号/密码）
- `apps.teachers.TeacherProfile`（档案，主键 = user_id）

ID 契约（v2）：`teacher_id` 与 `user_id` 均为 canonical user_id。
不再写入 legacy `teacher` 表，也不做双写。
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from apps.common.enums import UserRole, UserStatus
from apps.teachers.models import TeacherProfile
from lib.db_manager.teacher_db import TeacherDB
from lib.db_manager.user_db import UserDB


class TeacherService:
    """导师业务逻辑层（canonical）"""

    @staticmethod
    def get_teacher(teacher_id: int) -> Optional[TeacherProfile]:
        """获取导师档案（teacher_id 即 canonical user_id）"""
        return TeacherDB.get_by_id(teacher_id)

    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[TeacherProfile]:
        """根据 user_id 获取导师档案"""
        return TeacherDB.get_by_user_id(user_id)

    @staticmethod
    def get_by_teacher_number(teacher_number: str) -> Optional[TeacherProfile]:
        """根据工号获取导师档案"""
        return TeacherDB.get_by_teacher_number(teacher_number)

    @staticmethod
    def list_teachers(page: int = 1, page_size: int = 20) -> dict:
        """查询导师列表（分页，导师目录对已认证用户公开）"""
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        offset = (page - 1) * page_size
        teachers = TeacherDB.list_all(limit=page_size, offset=offset)
        total = TeacherDB.count_all()
        return {
            "list": teachers,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    @transaction.atomic
    def create_teacher(
        username: str,
        password: str,
        teacher_number: str,
        name: str,
        college: str,
        title: str = "",
        research_area: str = "",
        profile: Optional[str] = None,
        graduation_direction: Optional[str] = None,
        thesis_topic: Optional[str] = None,
        student_requirement: Optional[str] = None,
    ) -> dict:
        """创建导师（同时创建 canonical User 与 TeacherProfile）

        Returns:
            {"user_id": <canonical user_id>, "teacher_id": <同一 canonical user_id>}
        """
        if UserDB.get_by_username(username) is not None:
            raise ValueError(f"用户名 {username} 已存在")
        if TeacherDB.get_by_teacher_number(teacher_number) is not None:
            raise ValueError(f"工号 {teacher_number} 已存在")
        if len(password) < 8:
            raise ValueError("密码长度至少8位")

        user_id = UserDB.create(
            username, password, int(UserRole.TEACHER), int(UserStatus.ACTIVE)
        )
        TeacherDB.create(
            user_id=user_id,
            teacher_number=teacher_number,
            name=name,
            college=college,
            title=title or "",
            research_area=research_area or "",
            profile=profile,
            graduation_direction=graduation_direction,
            thesis_topic=thesis_topic,
            student_requirement=student_requirement,
        )
        return {"user_id": user_id, "teacher_id": user_id}

    @staticmethod
    def update_teacher(teacher_id: int, **fields) -> int:
        """更新导师档案（工号/主键不允许修改），返回受影响行数"""
        fields.pop("id", None)
        fields.pop("pk", None)
        fields.pop("user_id", None)
        fields.pop("user", None)
        fields.pop("teacher_number", None)  # 工号不允许修改
        if not fields:
            return 0
        return TeacherDB.update(teacher_id, **fields)

    @staticmethod
    @transaction.atomic
    def delete_teacher(teacher_id: int) -> int:
        """软删除导师（档案 + 账号），保留历史外键关系"""
        teacher = TeacherDB.get_by_id(teacher_id)
        if teacher is None:
            return 0
        affected = TeacherDB.delete(teacher_id)
        UserDB.delete(teacher.user_id)
        return affected
