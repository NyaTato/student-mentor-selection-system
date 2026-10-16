"""Student Model - 学生信息表

字段与 model/sql/student.sql 100% 一致。
继承 Django Model，managed=False，不依赖 Migration。
"""
from django.db import models

from model.entity.base_model import BaseModel


class Student(BaseModel):
    """学生信息表"""

    user_id = models.BigIntegerField(verbose_name="关联用户ID（不用FK，由Service维护）")
    student_number = models.CharField(max_length=32, unique=True, verbose_name="学号")
    name = models.CharField(max_length=64, verbose_name="姓名")
    major = models.CharField(max_length=128, verbose_name="专业")
    class_name = models.CharField(max_length=64, verbose_name="班级")
    department = models.CharField(max_length=128, null=True, blank=True, verbose_name="院系")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="电话号码")

    class Meta:
        db_table = 'student'
        managed = False
        verbose_name = '学生'
        verbose_name_plural = verbose_name
