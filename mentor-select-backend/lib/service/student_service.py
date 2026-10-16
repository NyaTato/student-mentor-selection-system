"""Student Service - 学生业务逻辑层（canonical 实现）

唯一数据源：
- `apps.users.User`（账号/密码）
- `apps.students.StudentProfile`（档案，主键 = user_id）

ID 契约（v2）：`student_id` 与 `user_id` 均为 canonical user_id。
不再写入 legacy `student` / `student_profile` 表，也不做双写。
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from apps.common.enums import UserRole, UserStatus
from apps.students.models import StudentProfile
from apps.users.models import User
from lib.db_manager.student_db import StudentDB
from lib.db_manager.user_db import UserDB

# 内部调用哨兵：表示「不做角色裁剪」（仅供内部编排使用）。
# API 读取路径必须显式传 actor，否则匿名 actor（None）会被裁剪为空集。
_UNSCOPED = object()


class StudentService:
    """学生业务逻辑层（canonical）"""

    @staticmethod
    def get_student(student_id: int, actor=_UNSCOPED) -> Optional[StudentProfile]:
        """获取学生档案（student_id 即 canonical user_id）

        传入 ``actor`` 时按角色裁剪整条记录：学生仅本人、导师仅其申请人/录取人、
        管理员全部；匿名或无权限返回 ``None``（API 层统一转 404）。
        """
        if actor is _UNSCOPED:
            return StudentDB.get_by_id(student_id)
        return StudentDB.get_visible(actor, pk=student_id)

    @staticmethod
    def get_by_user_id(user_id: int, actor=_UNSCOPED) -> Optional[StudentProfile]:
        """根据 user_id 获取学生档案（传入 actor 时按角色裁剪）"""
        if actor is _UNSCOPED:
            return StudentDB.get_by_user_id(user_id)
        return StudentDB.get_visible(actor, user_id=user_id)

    @staticmethod
    def get_by_student_number(
        student_number: str, actor=_UNSCOPED
    ) -> Optional[StudentProfile]:
        """根据学号查询学生档案（传入 actor 时按角色裁剪）"""
        if actor is _UNSCOPED:
            return StudentDB.get_by_student_number(student_number)
        return StudentDB.get_visible(actor, student_number=student_number)

    @staticmethod
    def list_related_student_ids(teacher_user_id: int) -> set[int]:
        """查询与指定导师存在真实申请或录取关系的学生的 user_id 集合

        用于学生接口的字段级授权（phone 可见性）。授权关系的查询
        由 DBManager/Service 负责，View 不再直接查 Application / Admission。
        """
        return StudentDB.list_related_user_ids(teacher_user_id)

    @staticmethod
    def list_students(
        page: int = 1, page_size: int = 20, actor=_UNSCOPED
    ) -> dict:
        """查询学生列表（分页）

        传入 ``actor`` 时在「角色裁剪后的 queryset」上分页，
        因此 ``total``（COUNT）与 ``list`` 使用同一过滤条件，
        未授权记录不会通过总数泄露。
        """
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        offset = (page - 1) * page_size
        if actor is _UNSCOPED:
            students = StudentDB.list_all(limit=page_size, offset=offset)
            total = StudentDB.count_all()
        else:
            students = StudentDB.list_visible(actor, limit=page_size, offset=offset)
            total = StudentDB.count_visible(actor)
        return {
            "list": students,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    @transaction.atomic
    def create_student(
        username: str,
        password: str,
        student_number: str,
        name: str,
        major: str,
        class_name: str,
        phone: Optional[str] = None,
        department: Optional[str] = None,
    ) -> dict:
        """创建学生（同时创建 canonical User 与 StudentProfile）

        Returns:
            {"user_id": <canonical user_id>, "student_id": <同一 canonical user_id>}
        """
        if UserDB.get_by_username(username) is not None:
            raise ValueError(f"用户名 {username} 已存在")
        if StudentDB.get_by_student_number(student_number) is not None:
            raise ValueError(f"学号 {student_number} 已存在")
        if phone and StudentDB.get_by_phone(phone) is not None:
            raise ValueError("该手机号已被其他学生使用")
        if len(password) < 8:
            raise ValueError("密码长度至少8位")

        user_id = UserDB.create(
            username, password, int(UserRole.STUDENT), int(UserStatus.ACTIVE)
        )
        StudentDB.create(
            user_id=user_id,
            student_number=student_number,
            name=name,
            major=major,
            class_name=class_name,
            phone=phone,
            department=department,
        )
        return {"user_id": user_id, "student_id": user_id}

    @staticmethod
    def update_student(student_id: int, **fields) -> int:
        """更新学生档案（学号/主键不允许修改），返回受影响行数"""
        fields.pop("id", None)
        fields.pop("pk", None)
        fields.pop("user_id", None)
        fields.pop("user", None)
        fields.pop("student_number", None)  # 学号不允许修改
        if not fields:
            return 0
        phone = fields.get("phone")
        if phone:
            existing = StudentDB.get_by_phone(phone)
            if existing is not None and existing.pk != student_id:
                raise ValueError("该手机号已被其他学生使用")
        return StudentDB.update(student_id, **fields)

    @staticmethod
    def update_phone(student_id: int, phone: str) -> int:
        """更新电话号码（学生自助修改）

        唯一性校验：手机号不能与其他学生重复（排除自身）
        """
        if phone:
            existing = StudentDB.get_by_phone(phone)
            if existing is not None and existing.pk != student_id:
                raise ValueError("该手机号已被其他学生使用")
        return StudentDB.update(student_id, phone=phone)

    @staticmethod
    @transaction.atomic
    def delete_student(student_id: int) -> int:
        """软删除学生（档案 + 账号），保留历史外键关系

        不物理删除：历史申请/录取记录通过 canonical FK 关联到该档案与账号，
        硬删除会破坏历史可追溯性。
        """
        student = StudentDB.get_by_id(student_id)
        if student is None:
            return 0
        affected = StudentDB.delete(student_id)
        UserDB.delete(student.user_id)
        return affected
