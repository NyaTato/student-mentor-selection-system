"""Admin Service - 管理员业务逻辑层（canonical 实现）

唯一数据源：
- `apps.users.User`（账号/密码）
- `apps.users.AdminProfile`（档案，主键 = user_id）

ID 契约（v2）：`admin_id` 与 `user_id` 均为 canonical user_id。
不再写入 legacy `admin` 表，也不做双写。
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from apps.common.enums import UserRole, UserStatus
from apps.users.models import AdminProfile
from lib.db_manager.admin_db import AdminDB
from lib.db_manager.user_db import UserDB


class AdminService:
    """管理员业务逻辑层（canonical）"""

    @staticmethod
    def get_admin(admin_id: int) -> Optional[AdminProfile]:
        """获取管理员档案（admin_id 即 canonical user_id）"""
        return AdminDB.get_by_id(admin_id)

    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[AdminProfile]:
        """根据 user_id 获取管理员档案"""
        return AdminDB.get_by_user_id(user_id)

    @staticmethod
    def list_admins(page: int = 1, page_size: int = 20) -> dict:
        """查询管理员列表（分页）"""
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        offset = (page - 1) * page_size
        admins = AdminDB.list_all(limit=page_size, offset=offset)
        total = AdminDB.count_all()
        return {
            "list": admins,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    @transaction.atomic
    def create_admin(username: str, password: str, name: str) -> dict:
        """创建管理员（同时创建 canonical User 与 AdminProfile）

        Returns:
            {"user_id": <canonical user_id>, "admin_id": <同一 canonical user_id>}
        """
        if UserDB.get_by_username(username) is not None:
            raise ValueError(f"用户名 {username} 已存在")
        if len(password) < 8:
            raise ValueError("密码长度至少8位")

        user_id = UserDB.create(
            username, password, int(UserRole.ADMIN), int(UserStatus.ACTIVE)
        )
        AdminDB.create(user_id=user_id, name=name)
        return {"user_id": user_id, "admin_id": user_id}

    @staticmethod
    def update_admin(admin_id: int, **fields) -> int:
        """更新管理员档案（主键不允许修改），返回受影响行数"""
        fields.pop("id", None)
        fields.pop("pk", None)
        fields.pop("user_id", None)
        fields.pop("user", None)
        if not fields:
            return 0
        return AdminDB.update(admin_id, **fields)

    @staticmethod
    @transaction.atomic
    def delete_admin(admin_id: int) -> int:
        """软删除管理员（档案 + 账号），保留历史外键关系"""
        admin = AdminDB.get_by_id(admin_id)
        if admin is None:
            return 0
        affected = AdminDB.delete(admin_id)
        UserDB.delete(admin.user_id)
        return affected
