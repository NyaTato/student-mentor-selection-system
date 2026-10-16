"""
用户管理 Repository
"""
from apps.common.repositories import BaseRepository
from apps.users.models import AdminProfile, User


class UserRepository(BaseRepository):
    """用户 Repository"""

    model = User

    def get_queryset(self):
        # 默认 manager 已过滤软删除
        return self.model.objects.select_related("admin_profile").all()

    def get_by_username(self, username: str) -> User | None:
        """按用户名查询"""
        return self.get_queryset().filter(username=username).first()

    def get_with_profile(self, pk: int) -> User:
        """按主键查询并带出关联档案"""
        try:
            return self.get_queryset().get(pk=pk)
        except self.model.DoesNotExist as exc:
            from apps.common.exceptions import NotFoundError

            raise NotFoundError(f"User (id={pk}) 不存在") from exc


class AdminProfileRepository(BaseRepository):
    """管理员档案 Repository"""

    model = AdminProfile

    def get_queryset(self):
        return self.model.objects.select_related("user").all()

    def get_by_user_id(self, user_id: int) -> AdminProfile | None:
        """按 user_id 查询"""
        return self.get_queryset().filter(user_id=user_id).first()
