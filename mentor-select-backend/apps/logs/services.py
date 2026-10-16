"""
日志管理业务服务

操作日志和登录日志均为只读（只写不改），由系统内部写入。
- 操作日志：由业务操作触发记录
- 登录日志：由认证流程触发记录
"""
from __future__ import annotations

from apps.common.logger import get_logger
from apps.common.services import BaseService
from apps.logs.models import LoginLog, OperationLog
from apps.logs.repositories import LoginLogRepository, OperationLogRepository

logger = get_logger("logs.services")


class OperationLogService(BaseService):
    """操作日志业务服务（只读）"""

    repository = OperationLogRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询操作日志列表，默认按 ID 倒序"""
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> OperationLog:
        return self.repository.get_by_id(pk)

    def list_by_user(self, user_id: int):
        """按用户查询操作日志"""
        return self.repository.list_by_user(user_id)

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询操作日志"""
        return self.repository.list_by_academic_year(academic_year_id)

    def list_by_action(self, action: int):
        """按操作类型查询操作日志"""
        return self.repository.list_by_action(action)

    def list_by_target(self, target_type: str, target_id: int):
        """按操作对象查询操作日志"""
        return self.repository.list_by_target(target_type, target_id)


class LoginLogService(BaseService):
    """登录日志业务服务（只读）"""

    repository = LoginLogRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询登录日志列表，默认按 ID 倒序"""
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> LoginLog:
        return self.repository.get_by_id(pk)

    def list_by_user(self, user_id: int):
        """按用户查询登录日志"""
        return self.repository.list_by_user(user_id)

    def list_by_username(self, username: str):
        """按用户名查询登录日志"""
        return self.repository.list_by_username(username)

    def list_by_success(self, is_success: bool):
        """按成功/失败查询登录日志"""
        return self.repository.list_by_success(is_success)
