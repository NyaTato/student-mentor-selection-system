"""
系统枚举定义
依据 DATABASE.md 第四部分
"""
from django.db import models


class UserRole(models.IntegerChoices):
    STUDENT = 1, "学生"
    TEACHER = 2, "导师"
    ADMIN = 3, "管理员"


class UserStatus(models.IntegerChoices):
    USER_INACTIVE = 0, "未激活"
    ACTIVE = 1, "启用"
    DISABLED = 2, "禁用"


class SystemStateValue(models.IntegerChoices):
    INIT = 0, "初始状态"
    FIRST_ROUND_OPEN = 1, "第一轮开放"
    TEACHER_REVIEW = 2, "导师审核"
    SECOND_ROUND_OPEN = 3, "第二轮开放"
    AUTO_ASSIGN = 4, "自动分配"
    FINISHED = 5, "已完成"


class ApplicationRound(models.IntegerChoices):
    FIRST_ROUND = 1, "第一轮"
    SECOND_ROUND = 2, "第二轮"


class ApplicationStatus(models.IntegerChoices):
    PENDING = 1, "待处理"
    APPROVED = 2, "已通过"
    REJECTED = 3, "已拒绝"


class AdmissionSource(models.IntegerChoices):
    ADMIT_ROUND1 = 1, "第一轮录取"
    ADMIT_ROUND2 = 2, "第二轮录取"
    MANUAL = 3, "人工分配"
    AUTO_ASSIGNED = 4, "自动分配"


class AcademicYearStatus(models.IntegerChoices):
    INACTIVE = 0, "未激活"
    ACTIVE = 1, "激活"
    ARCHIVED = 2, "已归档"


class StateTransitionType(models.IntegerChoices):
    FORWARD = 1, "正向推进"
    ROLLBACK = 2, "回退"
    AUTO = 3, "自动"


class ImportTaskStatus(models.IntegerChoices):
    PENDING = 0, "待处理"
    PROCESSING = 1, "处理中"
    SUCCESS = 2, "成功"
    PARTIAL = 3, "部分成功"
    FAILED = 4, "失败"


class ImportRowStatus(models.IntegerChoices):
    SUCCESS = 1, "成功"
    FAILED = 2, "失败"


class AutoAssignmentStatus(models.IntegerChoices):
    RUNNING = 0, "运行中"
    SUCCESS = 1, "成功"
    PARTIAL = 2, "部分成功"
    FAILED = 3, "失败"
    REVOKED = 4, "已撤销"


class OperationAction(models.IntegerChoices):
    # 认证模块 10-19
    LOGIN = 10, "用户登录"
    LOGOUT = 11, "用户登出"
    CHANGE_PASSWORD = 12, "修改密码"
    # 申请模块 20-29
    SUBMIT_APPLICATION = 20, "提交申请"
    ACCEPT_STUDENT = 21, "录取学生"
    REJECT_STUDENT = 22, "拒绝学生"
    REVOKE_ADMISSION = 23, "撤销录取"
    MANUAL_ASSIGN = 24, "人工分配"
    AUTO_ASSIGN = 25, "自动分配"
    REVOKE_AUTO_ASSIGN = 26, "撤销自动分配"
    # 系统模块 30-39
    STATE_FORWARD = 30, "状态推进"
    STATE_ROLLBACK = 31, "状态回退"
    STATE_AUTO_SCHEDULED = 32, "自动状态切换"
    CONFIG_SCHEDULE = 33, "配置自动切换"
    TOGGLE_AUTO_SWITCH = 34, "启停自动切换"
    # 管理模块 40-49
    IMPORT_USERS = 40, "导入用户"
    CREATE_USER = 41, "创建用户"
    UPDATE_USER = 42, "更新用户"
    DISABLE_USER = 43, "禁用用户"
    UPDATE_QUOTA = 44, "修改名额"
    # 公告模块 50-59
    CREATE_ANNOUNCEMENT = 50, "发布公告"
    UPDATE_ANNOUNCEMENT = 51, "更新公告"
    PUBLISH_ANNOUNCEMENT = 52, "发布/取消公告"
    DELETE_ANNOUNCEMENT = 53, "删除公告"
    # 学年模块 60-69
    CREATE_ACADEMIC_YEAR = 60, "创建学年"
    ACTIVATE_ACADEMIC_YEAR = 61, "激活学年"
    CLOSE_ACADEMIC_YEAR = 62, "关闭学年"
    COPY_QUOTA = 63, "复制名额"
