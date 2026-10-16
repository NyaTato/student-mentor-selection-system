"""BaseModel - 公共字段基类

所有 Model 统一继承 BaseModel。
公共字段：id, created_at, updated_at（与 SQL 100% 一致）。

设计说明：
- 继承 Django Model（符合老师要求：Model 定义直接对应数据库表结构）
- abstract=True，作为基类被继承
- 子类设置 managed=False，不依赖 Django Migration
- 字段类型与 SQL 完全一致：BIGINT -> BigAutoField/BigIntegerField
- 时间字段为 Unix Timestamp 秒级（BigIntegerField），不用 DateTimeField
- 不用 auto_now/auto_now_add（时间由 Repository/Service 写入）
"""
from django.db import models


class BaseModel(models.Model):
    """公共字段基类（abstract）"""

    id = models.BigAutoField(primary_key=True, verbose_name="主键ID")
    created_at = models.BigIntegerField(verbose_name="创建时间（Unix Timestamp 秒级）")
    updated_at = models.BigIntegerField(verbose_name="更新时间（Unix Timestamp 秒级）")

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        """容错初始化：过滤掉非本 Model 字段的 kwargs。

        原因：v2 与 v1 共用 `user` 表（v1 schema 含 last_login/is_superuser
        等额外字段）。Repository 用 SELECT * 返回 v1 字段时，默认 __init__
        会抛 TypeError。这里静默过滤非字段 kwargs，保证 v2 在 v1 schema
        下也能正常加载（仅取本 Model 定义的字段）。
        """
        if kwargs:
            field_names = {f.name for f in self._meta.concrete_fields}
            filtered = {k: v for k, v in kwargs.items() if k in field_names}
            dropped = set(kwargs) - set(filtered)
            if dropped:
                # 仅在 debug 时可见；不影响业务
                import logging
                logging.getLogger("model.base").debug(
                    "%s.__init__ dropped non-field kwargs: %s",
                    self.__class__.__name__,
                    sorted(dropped),
                )
            super().__init__(*args, **filtered)
        else:
            super().__init__(*args, **kwargs)
