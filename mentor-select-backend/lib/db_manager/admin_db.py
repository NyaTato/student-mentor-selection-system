"""Admin DBManager - canonical ORM 适配器

唯一数据源为 `apps.users.AdminProfile`。
canonical profile 主键即 user_id（OneToOneField primary_key=True）。

历史 raw SQL（legacy `admin` 表）已移除，legacy 定义仅作归档。
"""
from __future__ import annotations

from typing import Optional

from apps.common.repositories import BaseRepository
from apps.users.models import AdminProfile


class AdminDB:
    """Admin 数据访问适配器（canonical ORM）"""

    @staticmethod
    def get_by_id(admin_id: int) -> Optional[AdminProfile]:
        """根据主键（= user_id）查询管理员档案"""
        return AdminProfile.objects.filter(pk=admin_id).first()

    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[AdminProfile]:
        """根据 user_id 查询管理员档案"""
        return AdminProfile.objects.filter(user_id=user_id).first()

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> list[AdminProfile]:
        """查询管理员列表（分页，按 user_id 降序）"""
        return list(AdminProfile.objects.order_by("-user_id")[offset : offset + limit])

    @staticmethod
    def count_all() -> int:
        """查询管理员总数（不含已软删除档案）"""
        return AdminProfile.objects.count()

    @staticmethod
    def create(user_id: int, name: str) -> int:
        """创建管理员档案，返回档案主键（= user_id）"""
        instance = AdminProfile.objects.create(user_id=user_id, name=name)
        return instance.pk

    @staticmethod
    def update(admin_id: int, **fields) -> int:
        """更新管理员档案字段，返回受影响行数（0 表示档案不存在）"""
        instance = AdminDB.get_by_id(admin_id)
        if instance is None or not fields:
            return 0
        BaseRepository(AdminProfile).update(instance, fields)
        return 1

    @staticmethod
    def delete(admin_id: int) -> int:
        """软删除管理员档案（保留历史外键关系），返回受影响行数"""
        instance = AdminDB.get_by_id(admin_id)
        if instance is None:
            return 0
        BaseRepository(AdminProfile).soft_delete(instance)
        return 1
