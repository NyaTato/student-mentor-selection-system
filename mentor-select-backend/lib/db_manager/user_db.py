"""User DBManager - canonical ORM 适配器

历史版本此文件通过 raw SQL 直连 legacy `user` 表（managed=False，v2 7 列 schema），
并运行时探测 v1/v2 schema。该做法已废弃：

- 唯一数据源是 canonical `apps.users.User`（Django Migration 管理）
- 所有写入走 Django ORM，密码统一由 `set_password`（canonical hashing）处理
- legacy `model/entity/*` 定义仅作历史归档，不再参与任何生产查询

保留 UserDB 类名与方法签名，便于 lib/service 层与既有调用方平滑切换。
"""
from __future__ import annotations

from typing import Optional

from apps.common.enums import UserStatus
from apps.users.models import User


class UserDB:
    """User 数据访问适配器（canonical ORM）

    查询默认过滤软删除记录（User.objects 为 SoftDeleteUserManager）。
    """

    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        """根据 ID 查询用户（不含已软删除用户）"""
        return User.objects.filter(pk=user_id).first()

    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        """根据用户名查询用户（登录用）"""
        return User.objects.filter(username=username).first()

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> list[User]:
        """查询用户列表（分页，按 id 降序）"""
        return list(User.objects.order_by("-id")[offset : offset + limit])

    @staticmethod
    def list_by_ids(user_ids: list[int]) -> list[User]:
        """根据 ID 列表批量查询用户（避免 N+1 查询）"""
        if not user_ids:
            return []
        return list(User.objects.filter(pk__in=list(user_ids)))

    @staticmethod
    def count_all() -> int:
        """查询用户总数（不含已软删除用户）"""
        return User.objects.count()

    @staticmethod
    def create(
        username: str,
        raw_password: str,
        role: int,
        status: int = int(UserStatus.ACTIVE),
    ) -> int:
        """创建用户并返回新用户 ID

        密码使用 Django canonical hashing（`set_password`），
        is_active 与 status 保持同步，保证被禁用用户无法通过 JWT 认证。
        """
        user = User(
            username=username,
            role=role,
            status=status,
            is_active=(status == int(UserStatus.ACTIVE)),
        )
        user.set_password(raw_password)
        user.save()
        return user.pk

    @staticmethod
    def update(user_id: int, **fields) -> int:
        """更新用户字段，返回受影响行数（0 表示用户不存在）

        注意：password 字段必须是已哈希值；业务层应通过 Service 的方法修改密码。
        """
        user = UserDB.get_by_id(user_id)
        if user is None:
            return 0
        if not fields:
            return 0
        for key, value in fields.items():
            setattr(user, key, value)
        if "status" in fields:
            user.is_active = fields["status"] == int(UserStatus.ACTIVE)
        user.version = (user.version or 0) + 1
        user.save()
        return 1

    @staticmethod
    def delete(user_id: int) -> int:
        """软删除用户（保留历史外键关系），返回受影响行数"""
        from apps.common.repositories import BaseRepository

        user = UserDB.get_by_id(user_id)
        if user is None:
            return 0
        BaseRepository(User).soft_delete(user)
        return 1
