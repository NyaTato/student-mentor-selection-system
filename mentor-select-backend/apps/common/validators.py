"""
自定义验证器

依据 PROJECT.md / DATABASE.md 字段规范定义：
- 学号: 6-12 位数字
- 工号: 4-10 位数字
- 手机号: 11 位中国手机号
- 姓名: 2-64 位中英文
- 学年: 形如 2024-2025
"""
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_student_number(value: str):
    """验证学号格式：6-12 位数字"""
    if not re.match(r"^\d{6,12}$", value or ""):
        raise ValidationError(_("学号必须是 6-12 位数字"))


def validate_teacher_number(value: str):
    """验证工号格式：4-10 位数字"""
    if not re.match(r"^\d{4,10}$", value or ""):
        raise ValidationError(_("工号必须是 4-10 位数字"))


def validate_phone(value: str):
    """验证中国手机号格式：1[3-9]xxxxxxxxx"""
    if not re.match(r"^1[3-9]\d{9}$", value or ""):
        raise ValidationError(_("手机号格式不正确"))


def validate_chinese_name(value: str):
    """验证姓名：2-64 位中英文/数字/点"""
    if not value or not value.strip():
        raise ValidationError(_("姓名不能为空"))
    if not re.match(r"^[\u4e00-\u9fa5A-Za-z·.\s]{2,64}$", value):
        raise ValidationError(_("姓名必须是 2-64 位中英文"))


def validate_academic_year_name(value: str):
    """验证学年名称格式：YYYY-YYYY"""
    if not re.match(r"^\d{4}-\d{4}$", value or ""):
        raise ValidationError(_("学年格式必须是 YYYY-YYYY"))
    parts = value.split("-")
    start, end = int(parts[0]), int(parts[1])
    if end != start + 1:
        raise ValidationError(_("学年结束年份必须是开始年份 + 1"))


def validate_quota(value: int):
    """验证导师名额：0-99 之间"""
    if value is None or value < 0:
        raise ValidationError(_("名额不能为负数"))
    if value > 99:
        raise ValidationError(_("名额不能超过 99"))


def validate_research_area(value: str):
    """验证研究方向长度"""
    if value and len(value) > 512:
        raise ValidationError(_("研究方向不能超过 512 个字符"))
