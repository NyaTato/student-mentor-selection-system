"""
Service 基类

Service 层位于 View 和 Repository 之间：
- View 只负责 HTTP 协议层（参数解析、调用 Service、返回 Response）
- Service 负责业务逻辑编排（事务、跨 Repository 协作、业务校验）
- Repository 负责数据库访问

特性：
- 默认持有 repository 实例
- 提供 transaction.atomic 装饰器包装事务
- 业务异常由 Service 主动抛出，由全局异常处理器统一转换
"""
from __future__ import annotations

from django.db import transaction

from apps.common.logger import get_logger
from apps.common.repositories import BaseRepository
from apps.monitoring.decorators import track_time

logger = get_logger("common.services")


class BaseService:
    """业务 Service 基类

    使用方式：
        class UserService(BaseService):
            repository = UserRepository()

            def login(self, username, password):
                user = self.repository.get_by_filters(username=username)
                if not user.check_password(password):
                    raise AuthenticationFailedError("密码错误")
                return user
    """

    repository: BaseRepository = None

    def __init__(self, repository: BaseRepository | None = None):
        if repository is not None:
            self.repository = repository
        if self.repository is None:
            raise ValueError(f"{self.__class__.__name__}.repository 未设置")

    @property
    def model(self):
        """关联的 Model 类"""
        return self.repository.model

    # ===== 查询 =====

    @track_time()
    def list(self, filters: dict | None = None, order_by: list | None = None):
        """列表查询"""
        return self.repository.list(filters=filters, order_by=order_by)

    @track_time()
    def get_by_id(self, pk: int):
        """按主键查询"""
        return self.repository.get_by_id(pk)

    @track_time()
    def get_by_id_or_none(self, pk: int):
        """按主键查询，不存在返回 None"""
        return self.repository.get_by_id_or_none(pk)

    # ===== 写入 =====

    @track_time()
    @transaction.atomic
    def create(self, validated_data: dict):
        """创建

        子类可重写以加入业务校验、关联资源创建等逻辑。
        """
        return self.repository.create(**validated_data)

    @track_time()
    @transaction.atomic
    def update(self, pk: int, validated_data: dict):
        """更新"""
        instance = self.repository.get_by_id(pk)
        return self.repository.update(instance, validated_data)

    @track_time()
    @transaction.atomic
    def delete(self, pk: int):
        """删除（默认软删除）"""
        instance = self.repository.get_by_id(pk)
        self.repository.soft_delete(instance)
        return instance
