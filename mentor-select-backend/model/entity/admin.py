"""Admin Model - 管理员信息表

字段与 model/sql/admin.sql 100% 一致。
继承 Django Model，managed=False，不依赖 Migration。
"""
from django.db import models

from model.entity.base_model import BaseModel


class Admin(BaseModel):
    """管理员信息表"""

    user_id = models.BigIntegerField(verbose_name="关联用户ID（不用FK，由Service维护）")
    name = models.CharField(max_length=64, verbose_name="姓名")

    class Meta:
        db_table = 'admin'
        managed = False
        verbose_name = '管理员'
        verbose_name_plural = verbose_name
