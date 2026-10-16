"""User Service - 用户业务逻辑层（canonical 实现）

唯一数据源：`apps.users.User`（Django Migration 管理）。
- 密码：Django canonical hashing（`set_password` / `check_password`）
- 禁用/删除：status 与 is_active 同步，软删除保留历史外键
- 不再读写 legacy `user` 表（managed=False 定义仅作归档）

本 Service 向 v2 API（api/views/user.py）提供与原实现一致的调用签名，
因此 View 层无需改写。
"""
from __future__ import annotations

from typing import Optional

from django.contrib.auth.hashers import check_password, make_password

from apps.common.enums import UserRole, UserStatus
from apps.users.models import User
from lib.db_manager.user_db import UserDB


def _hash_password(password: str) -> str:
    """生成 Django canonical 密码哈希（pbkdf2_sha256$...）

    与 v1 AuthService 的 `user.check_password` 兼容，
    保证 v2 创建的用户可以通过 v1 auth 接口登录。
    """
    return make_password(password)


def _verify_password(password: str, stored: str) -> bool:
    """校验密码（支持 Django 所有内置 hasher）"""
    return check_password(password, stored)


class UserService:
    """用户业务逻辑层（canonical）"""

    @staticmethod
    def login(username: str, password: str) -> Optional[User]:
        """用户登录验证：用户名 + 密码 + 账号状态"""
        user = UserDB.get_by_username(username)
        if user is None:
            return None
        if user.status != int(UserStatus.ACTIVE) or not user.is_active:
            return None
        if not _verify_password(password, user.password):
            return None
        return user

    @staticmethod
    def get_user(user_id: int) -> Optional[User]:
        """获取用户信息（不含已软删除用户）"""
        return UserDB.get_by_id(user_id)

    @staticmethod
    def list_users(page: int = 1, page_size: int = 20) -> dict:
        """查询用户列表（分页）"""
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        offset = (page - 1) * page_size
        users = UserDB.list_all(limit=page_size, offset=offset)
        total = UserDB.count_all()
        return {
            "list": users,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def create_user(username: str, password: str, role: int) -> int:
        """创建用户，返回 canonical user_id"""
        if role not in (
            int(UserRole.STUDENT),
            int(UserRole.TEACHER),
            int(UserRole.ADMIN),
        ):
            raise ValueError("无效的角色")
        if UserDB.get_by_username(username) is not None:
            raise ValueError(f"用户名 {username} 已存在")
        if len(password) < 8:
            raise ValueError("密码长度至少8位")
        return UserDB.create(username, password, role, int(UserStatus.ACTIVE))

    @staticmethod
    def update_user(user_id: int, **fields) -> int:
        """更新用户信息（不允许直接改密码 / 主键）"""
        fields.pop("password", None)
        fields.pop("id", None)
        fields.pop("pk", None)
        fields.pop("username", None)
        if not fields:
            return 0
        return UserDB.update(user_id, **fields)

    @staticmethod
    def change_password(user_id: int, old_password: str, new_password: str) -> bool:
        """修改密码（校验旧密码）"""
        user = UserDB.get_by_id(user_id)
        if user is None:
            return False
        if not _verify_password(old_password, user.password):
            return False
        if len(new_password) < 8:
            raise ValueError("新密码长度至少8位")
        user.set_password(new_password)
        user.version = (user.version or 0) + 1
        user.save(update_fields=["password", "version", "updated_at"])
        return True

    @staticmethod
    def reset_password(user_id: int, new_password: str) -> int:
        """重置密码（管理员用，无需旧密码）"""
        if len(new_password) < 8:
            raise ValueError("新密码长度至少8位")
        user = UserDB.get_by_id(user_id)
        if user is None:
            return 0
        user.set_password(new_password)
        user.version = (user.version or 0) + 1
        user.save(update_fields=["password", "version", "updated_at"])
        return 1

    @staticmethod
    def disable_user(user_id: int) -> int:
        """禁用用户：status=DISABLED 且 is_active=False（使既有 JWT 立即失效）"""
        user = UserDB.get_by_id(user_id)
        if user is None:
            return 0
        user.status = int(UserStatus.DISABLED)
        user.is_active = False
        user.version = (user.version or 0) + 1
        user.save(update_fields=["status", "is_active", "version", "updated_at"])
        return 1

    @staticmethod
    def enable_user(user_id: int) -> int:
        """启用用户：status=ACTIVE 且 is_active=True"""
        user = UserDB.get_by_id(user_id)
        if user is None:
            return 0
        user.status = int(UserStatus.ACTIVE)
        user.is_active = True
        user.version = (user.version or 0) + 1
        user.save(update_fields=["status", "is_active", "version", "updated_at"])
        return 1

    @staticmethod
    def delete_user(user_id: int) -> int:
        """删除用户（软删除，保留历史申请/录取外键关系）"""
        return UserDB.delete(user_id)
