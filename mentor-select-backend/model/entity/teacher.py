"""Teacher Model - 导师信息表

字段与 model/sql/teacher.sql 100% 一致。
继承 Django Model，managed=False，不依赖 Migration。
"""
from django.db import models

from model.entity.base_model import BaseModel


class Teacher(BaseModel):
    """导师信息表"""

    user_id = models.BigIntegerField(verbose_name="关联用户ID（不用FK，由Service维护）")
    teacher_number = models.CharField(max_length=32, unique=True, verbose_name="工号")
    name = models.CharField(max_length=64, verbose_name="姓名")
    college = models.CharField(max_length=128, verbose_name="学院")
    title = models.CharField(max_length=64, default='', verbose_name="职称")
    research_area = models.CharField(max_length=512, default='', verbose_name="研究方向")
    profile = models.TextField(null=True, blank=True, verbose_name="个人简介")
    graduation_direction = models.CharField(max_length=512, null=True, blank=True, verbose_name="毕业设计方向")
    thesis_topic = models.CharField(max_length=512, null=True, blank=True, verbose_name="论文题目")
    student_requirement = models.CharField(max_length=512, null=True, blank=True, verbose_name="对学生要求")

    class Meta:
        db_table = 'teacher'
        managed = False
        verbose_name = '导师'
        verbose_name_plural = verbose_name
