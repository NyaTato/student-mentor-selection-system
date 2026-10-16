"""Constant 模块 - 常量集中维护

禁止 Magic Number，禁止 Magic String。
所有枚举、常量统一放这里。
"""
from constant.user_constant import UserRole, UserStatus

__all__ = ["UserRole", "UserStatus"]
