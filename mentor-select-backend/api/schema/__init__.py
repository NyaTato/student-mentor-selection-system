"""api/schema - Serializer 校验层

统一管理所有 API 接口的入参校验。
"""
from .data_schema import *  # noqa: F401,F403
from .data_schema import (  # noqa: F401
    AdminCreateSerializer,
    AdminListQuerySerializer,
    AdminUpdateSerializer,
    ChangePasswordSerializer,
    IdSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    StudentCreateSerializer,
    StudentListQuerySerializer,
    StudentPhoneUpdateSerializer,
    StudentUpdateSerializer,
    TeacherCreateSerializer,
    TeacherListQuerySerializer,
    TeacherUpdateSerializer,
    UserCreateSerializer,
    UserListQuerySerializer,
    UserUpdateSerializer,
)
