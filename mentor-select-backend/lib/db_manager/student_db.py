"""Student DBManager - canonical ORM 适配器

唯一数据源为 `apps.students.StudentProfile`。
canonical profile 主键即 user_id（OneToOneField primary_key=True），
因此 `student_id` 与 `user_id` 在本适配器中始终是同一个值。

历史 raw SQL（legacy `student` 表）已移除，legacy 定义仅作归档。
"""
from __future__ import annotations

from typing import Optional

from apps.common.enums import UserRole
from apps.common.repositories import BaseRepository
from apps.students.models import StudentProfile


class StudentDB:
    """Student 数据访问适配器（canonical ORM）"""

    @staticmethod
    def get_by_id(student_id: int) -> Optional[StudentProfile]:
        """根据主键（= user_id）查询学生档案"""
        return StudentProfile.objects.filter(pk=student_id).first()

    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[StudentProfile]:
        """根据 user_id 查询学生档案"""
        return StudentProfile.objects.filter(user_id=user_id).first()

    @staticmethod
    def get_by_student_number(student_number: str) -> Optional[StudentProfile]:
        """根据学号查询学生档案"""
        return StudentProfile.objects.filter(student_number=student_number).first()

    # ===== 角色裁剪（整条记录，而非单个字段） =====

    @staticmethod
    def visible_queryset(actor) -> "QuerySet[StudentProfile]":
        """按请求方角色返回**整条记录**可见的学生档案 queryset

        规则（review-checkpoints.md 最终评审要求）：
        - 管理员：全部学生
        - 学生：仅本人（canonical 主键即 user_id）
        - 导师：仅「与自己存在真实申请或录取关系」的学生
        - 匿名 / 其它角色：空集（不可见 = 后续统一转 404）

        裁剪在 **queryset 层**完成，因此分页总数（COUNT）与当页数据使用同一
        过滤条件，未授权记录既不会出现在 ``list`` 中，也不会被计入 ``total``。
        """
        if not getattr(actor, "is_authenticated", False):
            return StudentProfile.objects.none()

        role = getattr(actor, "role", None)
        user_id = getattr(actor, "id", None)
        if user_id is None:
            return StudentProfile.objects.none()

        if role == int(UserRole.ADMIN):
            return StudentProfile.objects.all()
        if role == int(UserRole.STUDENT):
            return StudentProfile.objects.filter(pk=user_id)
        if role == int(UserRole.TEACHER):
            related_ids = StudentDB.list_related_user_ids(user_id)
            return StudentProfile.objects.filter(pk__in=related_ids)
        return StudentProfile.objects.none()

    @staticmethod
    def get_visible(actor, **filters) -> Optional[StudentProfile]:
        """在「角色裁剪后」的范围内按条件查询单条档案（不可见 = None）"""
        return StudentDB.visible_queryset(actor).filter(**filters).first()

    @staticmethod
    def list_visible(actor, limit: int = 100, offset: int = 0) -> list[StudentProfile]:
        """在「角色裁剪后」的范围内分页查询（按 user_id 降序）"""
        return list(
            StudentDB.visible_queryset(actor).order_by("-user_id")[offset : offset + limit]
        )

    @staticmethod
    def count_visible(actor) -> int:
        """在「角色裁剪后」的范围内统计总数（供分页 total 使用）"""
        return StudentDB.visible_queryset(actor).count()

    @staticmethod
    def get_by_phone(phone: str) -> Optional[StudentProfile]:
        """根据手机号查询学生档案（用于改号唯一性校验）"""
        if not phone:
            return None
        return StudentProfile.objects.filter(phone=phone).first()

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> list[StudentProfile]:
        """查询学生列表（分页，按 user_id 降序）"""
        return list(StudentProfile.objects.order_by("-user_id")[offset : offset + limit])

    @staticmethod
    def count_all() -> int:
        """查询学生总数（不含已软删除档案）"""
        return StudentProfile.objects.count()

    @staticmethod
    def list_related_user_ids(teacher_user_id: int) -> set[int]:
        """查询与指定导师存在真实申请或录取关系的学生的 user_id 集合

        用途：学生档案的字段级授权（phone 仅对本人 / 管理员 /
        与该学生存在真实申请或录取关系的导师可见）。原先该查询写在
        api/views/student.py 内直接 import Application / Admission，
        现下沉到 DBManager，View 只做请求/响应/权限。

        Returns:
            学生 user_id 集合（canonical 主键即 user_id）
        """
        from apps.applications.models import Application
        from apps.assignments.models import Admission

        application_ids = Application.objects.filter(
            teacher_id=teacher_user_id
        ).values_list("student_id", flat=True)
        admission_ids = Admission.objects.filter(
            teacher_id=teacher_user_id
        ).values_list("student_id", flat=True)
        return set(application_ids) | set(admission_ids)

    @staticmethod
    def create(
        user_id: int,
        student_number: str,
        name: str,
        major: str,
        class_name: str,
        phone: Optional[str] = None,
        department: Optional[str] = None,
    ) -> int:
        """创建学生档案，返回档案主键（= user_id）"""
        profile = StudentProfile.objects.create(
            user_id=user_id,
            student_number=student_number,
            name=name,
            major=major,
            class_name=class_name,
            phone=phone,
            department=department,
        )
        return profile.pk

    @staticmethod
    def update(student_id: int, **fields) -> int:
        """更新学生档案字段，返回受影响行数（0 表示档案不存在）"""
        profile = StudentDB.get_by_id(student_id)
        if profile is None or not fields:
            return 0
        repository = BaseRepository(StudentProfile)
        repository.update(profile, fields)
        return 1

    @staticmethod
    def delete(student_id: int) -> int:
        """软删除学生档案（保留历史外键关系），返回受影响行数"""
        profile = StudentDB.get_by_id(student_id)
        if profile is None:
            return 0
        BaseRepository(StudentProfile).soft_delete(profile)
        return 1
