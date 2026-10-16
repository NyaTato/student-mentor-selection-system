"""
日志管理 Repository

操作日志和登录日志均为只读（只写不改），无软删除，无乐观锁。
"""
from apps.common.repositories import ReadOnlyRepository
from apps.logs.models import LoginLog, OperationLog


class OperationLogRepository(ReadOnlyRepository):
    """操作日志 Repository（只读）"""

    model = OperationLog

    def get_queryset(self):
        return self.model.objects.select_related(
            "academic_year", "user"
        ).all()

    def list_by_user(self, user_id: int):
        """按用户查询操作日志"""
        return self.get_queryset().filter(user_id=user_id)

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询操作日志"""
        return self.get_queryset().filter(academic_year_id=academic_year_id)

    def list_by_action(self, action: int):
        """按操作类型查询操作日志"""
        return self.get_queryset().filter(action=action)

    def list_by_target(self, target_type: str, target_id: int):
        """按操作对象查询操作日志"""
        return self.get_queryset().filter(
            target_type=target_type, target_id=target_id
        )


class LoginLogRepository(ReadOnlyRepository):
    """登录日志 Repository（只读）"""

    model = LoginLog

    def get_queryset(self):
        return self.model.objects.select_related("user").all()

    def list_by_user(self, user_id: int):
        """按用户查询登录日志"""
        return self.get_queryset().filter(user_id=user_id)

    def list_by_username(self, username: str):
        """按用户名查询登录日志"""
        return self.get_queryset().filter(username=username)

    def list_by_success(self, is_success: bool):
        """按成功/失败查询登录日志"""
        return self.get_queryset().filter(is_success=is_success)
