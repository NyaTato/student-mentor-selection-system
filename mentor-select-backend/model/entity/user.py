"""User Model - 用户认证表

字段与 model/sql/user.sql 100% 一致。
继承 Django Model，managed=False，不依赖 Migration。
"""
from django.db import models

from model.entity.base_model import BaseModel


class User(BaseModel):
    """用户认证表"""

    username = models.CharField(max_length=64, unique=True, verbose_name="登录用户名")
    password = models.CharField(max_length=128, verbose_name="加盐哈希密码")
    role = models.PositiveSmallIntegerField(verbose_name="角色：1=学生，2=导师，3=管理员")
    status = models.PositiveSmallIntegerField(default=1, verbose_name="账号状态：1=正常，0=禁用")

    class Meta:
        db_table = 'user'
        managed = False  # 不依赖 Django Migration，表结构由手写 SQL 创建
        verbose_name = '用户'
        verbose_name_plural = verbose_name
