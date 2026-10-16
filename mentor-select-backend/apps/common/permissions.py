"""
权限基类

提供基于角色的权限控制（RBAC）。

权限矩阵（依据 PROJECT.md）：
- 学生：查看导师、提交申请、查看自己申请/录取结果、查看公告
- 导师：查看自己档案/名额/申请、审核申请、撤销录取
- 管理员：所有操作，包括用户管理、名额设置、状态切换、Excel 导入、自动分配

使用方式：
    class MyViewSet(BaseApiResponseViewSet):
        permission_classes = [IsAuthenticated, IsAdmin]
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.common.enums import UserRole


class IsAuthenticated(BasePermission):
    """已认证"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsStudent(BasePermission):
    """学生权限"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.STUDENT.value
        )


class IsTeacher(BasePermission):
    """导师权限"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.TEACHER.value
        )


class IsAdmin(BasePermission):
    """管理员权限"""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.ADMIN.value
        )


class IsAdminOrTeacher(BasePermission):
    """管理员或导师权限"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.role in (
            UserRole.ADMIN.value,
            UserRole.TEACHER.value,
        )


class IsAdminOrReadOnly(BasePermission):
    """管理员可写，其他已认证用户只读"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == UserRole.ADMIN.value


class IsOwnerOrReadOnly(BasePermission):
    """资源所有者可写，其他已认证用户只读

    要求模型有 user 外键或与 User 关联的 profile。
    has_object_permission 默认查找 instance.user / instance.student / instance.teacher 字段。
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # 优先匹配常见关联字段
        owner = (
            getattr(obj, "user", None)
            or getattr(obj, "student", None)
            or getattr(obj, "teacher", None)
        )
        if owner is None:
            return False
        owner_id = getattr(owner, "id", None) or getattr(owner, "pk", None)
        return owner_id == request.user.id


class IsOwner(BasePermission):
    """仅资源所有者可访问（包括读）

    用于学生查看自己的申请、导师查看自己收到的申请等场景。
    """

    def has_object_permission(self, request, view, obj):
        owner = (
            getattr(obj, "user", None)
            or getattr(obj, "student", None)
            or getattr(obj, "teacher", None)
        )
        if owner is None:
            return False
        owner_id = getattr(owner, "id", None) or getattr(owner, "pk", None)
        return owner_id == request.user.id


class HasActiveStatus(BasePermission):
    """账户状态必须为启用"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        from apps.common.enums import UserStatus

        return request.user.status == UserStatus.ACTIVE.value
