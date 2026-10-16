"""data_schema.py - 所有 Serializer 统一存放
"""
import re

from rest_framework import serializers

from constant.user_constant import UserRole, UserStatus


# ====================================================================
# 通用字段约束（与 Database-Design.md 字段定义 100% 一致）
# ====================================================================
USERNAME_MAX_LENGTH = 64
PASSWORD_MAX_LENGTH = 128
PASSWORD_MIN_LENGTH = 8
NAME_MAX_LENGTH = 64
STUDENT_NUMBER_MAX_LENGTH = 32
TEACHER_NUMBER_MAX_LENGTH = 32
MAJOR_MAX_LENGTH = 128
CLASS_NAME_MAX_LENGTH = 64
PHONE_MAX_LENGTH = 20
COLLEGE_MAX_LENGTH = 128
TITLE_MAX_LENGTH = 64
RESEARCH_AREA_MAX_LENGTH = 512
GRADUATION_DIRECTION_MAX_LENGTH = 512
THESIS_TOPIC_MAX_LENGTH = 512
STUDENT_REQUIREMENT_MAX_LENGTH = 512

# ====================================================================
# 格式验证正则
# ====================================================================
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
STUDENT_NUMBER_PATTERN = re.compile(r'^[a-zA-Z0-9]{6,20}$')
TEACHER_NUMBER_PATTERN = re.compile(r'^[a-zA-Z0-9]{6,20}$')
PHONE_PATTERN = re.compile(r'^1[3-9]\d{9}$')


# ====================================================================
# User Serializer
# ====================================================================
class LoginSerializer(serializers.Serializer):
    """登录请求参数校验"""
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH, required=True)
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)


class UserCreateSerializer(serializers.Serializer):
    """创建用户请求参数校验"""
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH, required=True)
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)
    role = serializers.IntegerField(required=True)

    def validate_role(self, value: int) -> int:
        if value not in (UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN):
            raise serializers.ValidationError("角色无效：1=学生，2=导师，3=管理员")
        return value

    def validate_password(self, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise serializers.ValidationError(f"密码长度至少 {PASSWORD_MIN_LENGTH} 位")
        return value


class UserUpdateSerializer(serializers.Serializer):
    """更新用户请求参数校验（不允许修改密码、用户名）"""
    role = serializers.IntegerField(required=False)
    status = serializers.IntegerField(required=False)

    def validate_role(self, value: int) -> int:
        if value not in (UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN):
            raise serializers.ValidationError("角色无效：1=学生，2=导师，3=管理员")
        return value

    def validate_status(self, value: int) -> int:
        if value not in (UserStatus.ACTIVE, UserStatus.DISABLED):
            raise serializers.ValidationError("状态无效：1=正常，0=禁用")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码请求参数校验"""
    old_password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)
    new_password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)

    def validate_new_password(self, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise serializers.ValidationError(f"新密码长度至少 {PASSWORD_MIN_LENGTH} 位")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """重置密码请求参数校验（管理员用，无需旧密码）"""
    new_password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)

    def validate_new_password(self, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise serializers.ValidationError(f"新密码长度至少 {PASSWORD_MIN_LENGTH} 位")
        return value


class UserListQuerySerializer(serializers.Serializer):
    """用户列表查询参数校验"""
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


# ====================================================================
# Student Serializer
# ====================================================================
class StudentCreateSerializer(serializers.Serializer):
    """创建学生请求参数校验（同时创建 User 和 Student）"""
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH, required=True)
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)
    student_number = serializers.CharField(max_length=STUDENT_NUMBER_MAX_LENGTH, required=True)
    name = serializers.CharField(max_length=NAME_MAX_LENGTH, required=True)
    major = serializers.CharField(max_length=MAJOR_MAX_LENGTH, required=True)
    class_name = serializers.CharField(max_length=CLASS_NAME_MAX_LENGTH, required=True)
    department = serializers.CharField(max_length=COLLEGE_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=PHONE_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)

    def validate_username(self, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise serializers.ValidationError("用户名只能包含字母、数字、下划线，长度3-20位")
        return value

    def validate_password(self, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise serializers.ValidationError(f"密码长度至少 {PASSWORD_MIN_LENGTH} 位")
        return value

    def validate_student_number(self, value: str) -> str:
        if not STUDENT_NUMBER_PATTERN.match(value):
            raise serializers.ValidationError("学号只能包含字母和数字，长度6-20位")
        return value

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("姓名不能为空")
        return value

    def validate_major(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("专业不能为空")
        return value

    def validate_class_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("班级不能为空")
        return value

    def validate_phone(self, value: str) -> str:
        if value and not PHONE_PATTERN.match(value):
            raise serializers.ValidationError("手机号格式不正确（应为11位数字，1开头）")
        return value


class StudentUpdateSerializer(serializers.Serializer):
    """更新学生请求参数校验（不允许修改 student_number、user_id）"""
    name = serializers.CharField(max_length=NAME_MAX_LENGTH, required=False)
    major = serializers.CharField(max_length=MAJOR_MAX_LENGTH, required=False)
    class_name = serializers.CharField(max_length=CLASS_NAME_MAX_LENGTH, required=False)
    department = serializers.CharField(max_length=COLLEGE_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)


class StudentPhoneUpdateSerializer(serializers.Serializer):
    """更新学生电话请求参数校验（学生自助修改）"""
    phone = serializers.CharField(max_length=PHONE_MAX_LENGTH, required=True, allow_blank=False)

    def validate_phone(self, value: str) -> str:
        if not PHONE_PATTERN.match(value):
            raise serializers.ValidationError("手机号格式不正确（应为11位数字，1开头）")
        return value


class StudentListQuerySerializer(serializers.Serializer):
    """学生列表查询参数校验"""
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


# ====================================================================
# Teacher Serializer
# ====================================================================
class TeacherCreateSerializer(serializers.Serializer):
    """创建导师请求参数校验（同时创建 User 和 Teacher）"""
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH, required=True)
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)
    teacher_number = serializers.CharField(max_length=TEACHER_NUMBER_MAX_LENGTH, required=True)
    name = serializers.CharField(max_length=NAME_MAX_LENGTH, required=True)
    college = serializers.CharField(max_length=COLLEGE_MAX_LENGTH, required=True)
    title = serializers.CharField(max_length=TITLE_MAX_LENGTH, required=False, allow_blank=True, default='')
    research_area = serializers.CharField(max_length=RESEARCH_AREA_MAX_LENGTH, required=False, allow_blank=True, default='')
    profile = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    graduation_direction = serializers.CharField(max_length=GRADUATION_DIRECTION_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)
    thesis_topic = serializers.CharField(max_length=THESIS_TOPIC_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)
    student_requirement = serializers.CharField(max_length=STUDENT_REQUIREMENT_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)

    def validate_username(self, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise serializers.ValidationError("用户名只能包含字母、数字、下划线，长度3-20位")
        return value

    def validate_password(self, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise serializers.ValidationError(f"密码长度至少 {PASSWORD_MIN_LENGTH} 位")
        return value

    def validate_teacher_number(self, value: str) -> str:
        if not TEACHER_NUMBER_PATTERN.match(value):
            raise serializers.ValidationError("工号只能包含字母和数字，长度6-20位")
        return value

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("姓名不能为空")
        return value

    def validate_college(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("所属学院不能为空")
        return value


class TeacherUpdateSerializer(serializers.Serializer):
    """更新导师请求参数校验（不允许修改 teacher_number、user_id）"""
    name = serializers.CharField(max_length=NAME_MAX_LENGTH, required=False)
    college = serializers.CharField(max_length=COLLEGE_MAX_LENGTH, required=False)
    title = serializers.CharField(max_length=TITLE_MAX_LENGTH, required=False, allow_blank=True)
    research_area = serializers.CharField(max_length=RESEARCH_AREA_MAX_LENGTH, required=False, allow_blank=True)
    profile = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    graduation_direction = serializers.CharField(max_length=GRADUATION_DIRECTION_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)
    thesis_topic = serializers.CharField(max_length=THESIS_TOPIC_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)
    student_requirement = serializers.CharField(max_length=STUDENT_REQUIREMENT_MAX_LENGTH, required=False, allow_null=True, allow_blank=True)


class TeacherListQuerySerializer(serializers.Serializer):
    """导师列表查询参数校验"""
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


# ====================================================================
# Admin Serializer
# ====================================================================
class AdminCreateSerializer(serializers.Serializer):
    """创建管理员请求参数校验（同时创建 User 和 Admin）"""
    username = serializers.CharField(max_length=USERNAME_MAX_LENGTH, required=True)
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, required=True, write_only=True)
    name = serializers.CharField(max_length=NAME_MAX_LENGTH, required=True)

    def validate_username(self, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise serializers.ValidationError("用户名只能包含字母、数字、下划线，长度3-20位")
        return value

    def validate_password(self, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise serializers.ValidationError(f"密码长度至少 {PASSWORD_MIN_LENGTH} 位")
        return value

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("姓名不能为空")
        return value


class AdminUpdateSerializer(serializers.Serializer):
    """更新管理员请求参数校验（不允许修改 user_id）"""
    name = serializers.CharField(max_length=NAME_MAX_LENGTH, required=False)


class AdminListQuerySerializer(serializers.Serializer):
    """管理员列表查询参数校验"""
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


# ====================================================================
# 通用 ID 参数校验（用于 delete/disable/enable 等仅接收路径 ID 的接口）
# ====================================================================
class IdSerializer(serializers.Serializer):
    """通用 ID 参数校验

    用于 delete/disable/enable 等接口，从路径参数构造 data 进行校验，
    确保 ID 为正整数。
    """
    id = serializers.IntegerField(required=True, min_value=1)
