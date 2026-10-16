"""Excel 导入列定义

依据 PROJECT.md 2.1-2.3 用户角色字段 + DATABASE.md user/student_profile/teacher_profile/admin_profile 表。

Excel 模板列顺序固定，表头为中文。每行一个用户记录。
"""
from __future__ import annotations

from apps.common.enums import UserRole

# 文件级限制（PROJECT.md 7.13）
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_ROW_COUNT = 5000

# 默认初始密码长度
DEFAULT_PASSWORD_LENGTH = 8


# 各角色 Excel 列定义（顺序即列顺序）
# (字段名, 表头, 是否必填, 最大长度, 说明)
STUDENT_COLUMNS = [
    ("username", "用户名(学号)", True, 64, "登录用户名，6-12 位数字"),
    ("password", "初始密码", False, 128, "留空则使用学号作为初始密码"),
    ("name", "姓名", True, 64, "2-64 位中英文"),
    ("student_number", "学号", True, 32, "6-12 位数字，需与用户名一致"),
    ("major", "专业", True, 128, "所属专业"),
    ("class_name", "班级", True, 64, "所属班级"),
]

TEACHER_COLUMNS = [
    ("username", "用户名(工号)", True, 64, "登录用户名，4-10 位数字"),
    ("password", "初始密码", False, 128, "留空则使用工号作为初始密码"),
    ("name", "姓名", True, 64, "2-64 位中英文"),
    ("teacher_number", "工号", True, 32, "4-10 位数字，需与用户名一致"),
    ("college", "学院", True, 128, "所属学院"),
    ("title", "职称", False, 64, "如：教授/副教授/讲师"),
    ("research_area", "研究方向", False, 512, "多个方向用逗号分隔"),
]

ADMIN_COLUMNS = [
    ("username", "用户名", True, 64, "登录用户名"),
    ("password", "初始密码", False, 128, "留空则使用用户名作为初始密码"),
    ("name", "姓名", True, 64, "2-64 位中英文"),
]


# 角色 -> 列定义映射
COLUMNS_BY_ROLE = {
    UserRole.STUDENT.value: STUDENT_COLUMNS,
    UserRole.TEACHER.value: TEACHER_COLUMNS,
    UserRole.ADMIN.value: ADMIN_COLUMNS,
}


def get_columns(role: int):
    """获取角色对应的列定义"""
    if role not in COLUMNS_BY_ROLE:
        raise ValueError(f"不支持的角色: {role}")
    return COLUMNS_BY_ROLE[role]


def get_headers(role: int) -> list[str]:
    """获取角色对应的表头列表"""
    return [col[1] for col in get_columns(role)]


def get_required_fields(role: int) -> list[str]:
    """获取角色对应的必填字段名"""
    return [col[0] for col in get_columns(role) if col[2]]
