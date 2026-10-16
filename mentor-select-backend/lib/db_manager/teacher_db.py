"""Teacher DBManager - canonical ORM 适配器

唯一数据源为 `apps.teachers.TeacherProfile`。
canonical profile 主键即 user_id（OneToOneField primary_key=True）。

历史 raw SQL（legacy `teacher` 表）已移除，legacy 定义仅作归档。
"""
from __future__ import annotations

from typing import Optional

from apps.common.repositories import BaseRepository
from apps.teachers.models import TeacherProfile


class TeacherDB:
    """Teacher 数据访问适配器（canonical ORM）"""

    @staticmethod
    def get_by_id(teacher_id: int) -> Optional[TeacherProfile]:
        """根据主键（= user_id）查询导师档案"""
        return TeacherProfile.objects.filter(pk=teacher_id).first()

    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[TeacherProfile]:
        """根据 user_id 查询导师档案"""
        return TeacherProfile.objects.filter(user_id=user_id).first()

    @staticmethod
    def get_by_teacher_number(teacher_number: str) -> Optional[TeacherProfile]:
        """根据工号查询导师档案"""
        return TeacherProfile.objects.filter(teacher_number=teacher_number).first()

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> list[TeacherProfile]:
        """查询导师列表（分页，按 user_id 降序）"""
        return list(TeacherProfile.objects.order_by("-user_id")[offset : offset + limit])

    @staticmethod
    def count_all() -> int:
        """查询导师总数（不含已软删除档案）"""
        return TeacherProfile.objects.count()

    @staticmethod
    def create(
        user_id: int,
        teacher_number: str,
        name: str,
        college: str,
        title: str = "",
        research_area: str = "",
        profile: Optional[str] = None,
        graduation_direction: Optional[str] = None,
        thesis_topic: Optional[str] = None,
        student_requirement: Optional[str] = None,
    ) -> int:
        """创建导师档案，返回档案主键（= user_id）"""
        instance = TeacherProfile.objects.create(
            user_id=user_id,
            teacher_number=teacher_number,
            name=name,
            college=college,
            title=title,
            research_area=research_area,
            profile=profile,
            graduation_direction=graduation_direction,
            thesis_topic=thesis_topic,
            student_requirement=student_requirement,
        )
        return instance.pk

    @staticmethod
    def update(teacher_id: int, **fields) -> int:
        """更新导师档案字段，返回受影响行数（0 表示档案不存在）"""
        instance = TeacherDB.get_by_id(teacher_id)
        if instance is None or not fields:
            return 0
        BaseRepository(TeacherProfile).update(instance, fields)
        return 1

    @staticmethod
    def delete(teacher_id: int) -> int:
        """软删除导师档案（保留历史外键关系），返回受影响行数"""
        instance = TeacherDB.get_by_id(teacher_id)
        if instance is None:
            return 0
        BaseRepository(TeacherProfile).soft_delete(instance)
        return 1
