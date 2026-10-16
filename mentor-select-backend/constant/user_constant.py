"""User 相关常量

角色和状态枚举，与 SQL COMMENT 保持一致。
"""


class UserRole:
    """用户角色枚举（对应 user.role 字段）"""

    STUDENT = 1   # 学生
    TEACHER = 2   # 导师
    ADMIN = 3     # 管理员

    CHOICES = (
        (STUDENT, "学生"),
        (TEACHER, "导师"),
        (ADMIN, "管理员"),
    )


class UserStatus:
    """账号状态枚举（对应 user.status 字段）"""

    DISABLED = 0  # 禁用
    ACTIVE = 1    # 正常

    CHOICES = (
        (DISABLED, "禁用"),
        (ACTIVE, "正常"),
    )
