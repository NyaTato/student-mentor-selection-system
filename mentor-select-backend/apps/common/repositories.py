"""
Repository 基类

封装常见 ORM 操作，将数据库访问集中到 Repository 层，
View → Serializer → Service → Repository → Model 五层架构。

特性：
- 软删除感知：基于模型的 deleted_at 字段，objects manager 默认过滤已删除记录
- 乐观锁：基于 version 字段，更新时校验版本号防止并发覆盖
- 类型注解：返回 Model 实例或 QuerySet，便于 IDE 推断
- 通用查询：get_by_id / get_by_filters / list / filter
- 通用写入：create / update / soft_delete / hard_delete / bulk_create

层次结构（LSP 合规）：
    ReadOnlyRepositoryBase          ← 仅查询方法
        └── BaseRepository          ← 添加写入方法（create/update/delete）
        └── AppendOnlyRepositoryBase ← 仅添加 create/bulk_create（无 update/delete）
    ReadOnlyRepository              ← = ReadOnlyRepositoryBase（别名，向后兼容）

LSP 合规原则：
- 只读基类不暴露写方法（而非通过 NotImplementedError 屏蔽）
- 只追加基类不暴露 update/delete（而非通过 NotImplementedError 屏蔽）
- 共享的 create/bulk_create 实现通过 _CreateMixin 组合，避免代码重复
"""
from __future__ import annotations

from django.db import models, transaction
from django.db.models import QuerySet

from apps.common.exceptions import ConflictError, NotFoundError
from apps.common.logger import get_logger
from apps.monitoring.decorators import track_time

logger = get_logger("common.repositories")


class _CreateMixin:
    """创建记录的 Mixin

    提供 create 和 bulk_create 方法，供 BaseRepository 和 AppendOnlyRepositoryBase 共享，
    避免代码重复（Dried Code）。
    """

    model: type[models.Model]

    @track_time(metric_type="repository")
    @transaction.atomic
    def create(self, **data) -> models.Model:
        """创建记录"""
        instance = self.model(**data)
        instance.save()
        logger.debug("Created %s id=%s", self.model.__name__, instance.pk)
        return instance

    @track_time(metric_type="repository")
    @transaction.atomic
    def bulk_create(self, objs: list[models.Model]) -> list[models.Model]:
        """批量创建"""
        return self.model.objects.bulk_create(objs)


class ReadOnlyRepositoryBase:
    """只读 Repository 基类（仅查询方法）

    LSP 合规：不暴露 create/update/delete，
    子类若需要写入应继承 BaseRepository 或 AppendOnlyRepositoryBase。

    使用方式：
        class UserRepository(BaseRepository):
            model = User

        repo = UserRepository()
        user = repo.get_by_id(1)
    """

    model: type[models.Model] = None

    def __init__(self, model: type[models.Model] | None = None):
        if model is not None:
            self.model = model
        if self.model is None:
            raise ValueError(f"{self.__class__.__name__}.model 未设置")

    # ===== 查询 =====

    @track_time(metric_type="repository")
    def get_queryset(self) -> QuerySet:
        """返回默认 queryset（软删除 manager 已过滤已删除记录）"""
        return self.model.objects.all()

    @track_time(metric_type="repository")
    def get_by_id(self, pk: int) -> models.Model:
        """按主键查询，不存在则抛 NotFoundError"""
        try:
            return self.get_queryset().get(pk=pk)
        except self.model.DoesNotExist as exc:
            raise NotFoundError(
                f"{self.model.__name__} (id={pk}) 不存在",
            ) from exc

    @track_time(metric_type="repository")
    def get_by_id_or_none(self, pk: int) -> models.Model | None:
        """按主键查询，不存在返回 None"""
        return self.get_queryset().filter(pk=pk).first()

    @track_time(metric_type="repository")
    def get_by_filters(self, **filters) -> models.Model:
        """按条件查询单条记录，不存在则抛 NotFoundError"""
        try:
            return self.get_queryset().get(**filters)
        except self.model.DoesNotExist as exc:
            raise NotFoundError(
                f"{self.model.__name__} 不存在 (filters={filters})",
            ) from exc

    @track_time(metric_type="repository")
    def get_by_filters_or_none(self, **filters) -> models.Model | None:
        """按条件查询单条记录，不存在返回 None"""
        return self.get_queryset().filter(**filters).first()

    @track_time(metric_type="repository")
    def list(self, filters: dict | None = None, order_by: list | None = None) -> QuerySet:
        """列表查询"""
        qs = self.get_queryset()
        if filters:
            qs = qs.filter(**filters)
        if order_by:
            qs = qs.order_by(*order_by)
        return qs

    @track_time(metric_type="repository")
    def filter(self, **filters) -> QuerySet:
        """条件查询"""
        return self.get_queryset().filter(**filters)

    @track_time(metric_type="repository")
    def exists(self, **filters) -> bool:
        """判断是否存在"""
        return self.get_queryset().filter(**filters).exists()

    @track_time(metric_type="repository")
    def count(self, **filters) -> int:
        """统计数量"""
        qs = self.get_queryset()
        if filters:
            qs = qs.filter(**filters)
        return qs.count()


class BaseRepository(ReadOnlyRepositoryBase, _CreateMixin):
    """通用 Repository 基类（查询 + 写入）

    继承 ReadOnlyRepositoryBase 的查询方法和 _CreateMixin 的创建方法，
    并添加 update/delete 方法。
    """

    # ===== 写入 =====

    @track_time(metric_type="repository")
    @transaction.atomic
    def update(
        self,
        instance: models.Model,
        data: dict,
        check_version: bool = False,
        expected_version: int | None = None,
    ) -> models.Model:
        """更新记录

        Args:
            instance: 待更新的实例
            data: 字段 -> 值
            check_version: 是否启用乐观锁校验
            expected_version: 预期的版本号（与 check_version 配合使用）
        """
        if check_version and expected_version is not None:
            current_version = getattr(instance, "version", None)
            if current_version is not None and current_version != expected_version:
                raise ConflictError(
                    "数据已被其他操作修改，请刷新后重试",
                )

        for attr, value in data.items():
            setattr(instance, attr, value)

        # 乐观锁版本 +1
        if hasattr(instance, "version"):
            instance.version = (instance.version or 0) + 1

        instance.save()
        logger.debug("Updated %s id=%s", self.model.__name__, instance.pk)
        return instance

    @track_time(metric_type="repository")
    @transaction.atomic
    def update_by_id(self, pk: int, data: dict) -> models.Model:
        """按主键更新"""
        instance = self.get_by_id(pk)
        return self.update(instance, data)

    @track_time(metric_type="repository")
    @transaction.atomic
    def soft_delete(self, instance: models.Model) -> None:
        """软删除（标记 deleted_at）

        要求模型有 deleted_at 字段。
        """
        if not hasattr(instance, "deleted_at"):
            # 模型未支持软删除，回退到硬删除
            instance.delete()
            return

        from django.utils import timezone

        instance.deleted_at = timezone.now()
        if hasattr(instance, "version"):
            instance.version = (instance.version or 0) + 1
        instance.save(update_fields=["deleted_at", "version", "updated_at"])
        logger.debug("Soft deleted %s id=%s", self.model.__name__, instance.pk)

    @track_time(metric_type="repository")
    @transaction.atomic
    def soft_delete_by_id(self, pk: int) -> None:
        """按主键软删除"""
        instance = self.get_by_id(pk)
        self.soft_delete(instance)

    @track_time(metric_type="repository")
    @transaction.atomic
    def hard_delete(self, instance: models.Model) -> None:
        """硬删除（物理删除）"""
        instance.delete()
        logger.debug("Hard deleted %s id=%s", self.model.__name__, instance.pk)

    @track_time(metric_type="repository")
    @transaction.atomic
    def hard_delete_by_id(self, pk: int) -> None:
        """按主键硬删除"""
        instance = self.get_by_id(pk)
        self.hard_delete(instance)


class AppendOnlyRepositoryBase(ReadOnlyRepositoryBase, _CreateMixin):
    """只追加 Repository 基类（查询 + create + bulk_create，无 update/delete）

    LSP 合规：不暴露 update/delete 方法。
    用于日志类、历史记录类模型（StateHistory、ImportLog 等）。

    通过 _CreateMixin 共享 create/bulk_create 实现，避免与 BaseRepository 代码重复。
    """
    pass


# 向后兼容别名：ReadOnlyRepository = ReadOnlyRepositoryBase
# 不再通过 NotImplementedError 屏蔽写方法，而是根本不暴露写方法（LSP 合规）
# 注意：新代码应直接使用 ReadOnlyRepositoryBase，本别名保留用于向后兼容
ReadOnlyRepository = ReadOnlyRepositoryBase
