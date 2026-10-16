"""
通用权限测试
覆盖 apps/common/permissions.py 中所有权限类

权限矩阵：
- IsAuthenticated: 已认证即可
- IsStudent / IsTeacher / IsAdmin: 单角色校验
- IsAdminOrTeacher: 管理员或导师
- IsAdminOrReadOnly: 管理员可写，其他已认证只读
- IsOwnerOrReadOnly: 所有者可写，其他已认证只读
- IsOwner: 仅所有者（含读）
- HasActiveStatus: 账户状态为启用
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.common.enums import UserRole, UserStatus
from apps.common.permissions import (
    HasActiveStatus,
    IsAdmin,
    IsAdminOrReadOnly,
    IsAdminOrTeacher,
    IsAuthenticated,
    IsOwner,
    IsOwnerOrReadOnly,
    IsStudent,
    IsTeacher,
)
from apps.users.models import User


class _DummyView:
    """用于权限测试的简单 view 占位"""


class _DummyObject:
    """用于 has_object_permission 测试的对象，模拟 user 关联"""

    def __init__(self, owner=None):
        self.user = owner


@pytest.fixture
def factory():
    return APIRequestFactory()


def _make_request(factory, method="get", user=None):
    """构造一个已设置 user 的请求"""
    request = getattr(factory, method.lower())("/")
    request.user = user if user is not None else AnonymousUser()
    return request


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="perm_admin",
        password="TestPass123!",
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="perm_teacher",
        password="TestPass123!",
        role=UserRole.TEACHER.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        username="perm_student",
        password="TestPass123!",
        role=UserRole.STUDENT.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def disabled_user(db):
    return User.objects.create_user(
        username="perm_disabled",
        password="TestPass123!",
        role=UserRole.STUDENT.value,
        status=UserStatus.DISABLED.value,
    )


@pytest.mark.django_db
class TestIsAuthenticated:
    """IsAuthenticated 权限测试"""

    def test_allows_authenticated_user(self, factory, student_user):
        request = _make_request(factory, user=student_user)
        perm = IsAuthenticated()
        assert perm.has_permission(request, _DummyView()) is True

    def test_rejects_anonymous(self, factory):
        request = _make_request(factory, user=AnonymousUser())
        perm = IsAuthenticated()
        assert perm.has_permission(request, _DummyView()) is False

    def test_allows_admin(self, factory, admin_user):
        request = _make_request(factory, user=admin_user)
        perm = IsAuthenticated()
        assert perm.has_permission(request, _DummyView()) is True

    def test_allows_teacher(self, factory, teacher_user):
        request = _make_request(factory, user=teacher_user)
        perm = IsAuthenticated()
        assert perm.has_permission(request, _DummyView()) is True


@pytest.mark.django_db
class TestIsStudent:
    """IsStudent 权限测试"""

    def test_allows_student(self, factory, student_user):
        request = _make_request(factory, user=student_user)
        assert IsStudent().has_permission(request, _DummyView()) is True

    def test_rejects_teacher(self, factory, teacher_user):
        request = _make_request(factory, user=teacher_user)
        assert IsStudent().has_permission(request, _DummyView()) is False

    def test_rejects_admin(self, factory, admin_user):
        request = _make_request(factory, user=admin_user)
        assert IsStudent().has_permission(request, _DummyView()) is False

    def test_rejects_anonymous(self, factory):
        request = _make_request(factory, user=AnonymousUser())
        assert IsStudent().has_permission(request, _DummyView()) is False


@pytest.mark.django_db
class TestIsTeacher:
    """IsTeacher 权限测试"""

    def test_allows_teacher(self, factory, teacher_user):
        request = _make_request(factory, user=teacher_user)
        assert IsTeacher().has_permission(request, _DummyView()) is True

    def test_rejects_student(self, factory, student_user):
        request = _make_request(factory, user=student_user)
        assert IsTeacher().has_permission(request, _DummyView()) is False

    def test_rejects_admin(self, factory, admin_user):
        request = _make_request(factory, user=admin_user)
        assert IsTeacher().has_permission(request, _DummyView()) is False

    def test_rejects_anonymous(self, factory):
        request = _make_request(factory, user=AnonymousUser())
        assert IsTeacher().has_permission(request, _DummyView()) is False


@pytest.mark.django_db
class TestIsAdmin:
    """IsAdmin 权限测试"""

    def test_allows_admin(self, factory, admin_user):
        request = _make_request(factory, user=admin_user)
        assert IsAdmin().has_permission(request, _DummyView()) is True

    def test_rejects_student(self, factory, student_user):
        request = _make_request(factory, user=student_user)
        assert IsAdmin().has_permission(request, _DummyView()) is False

    def test_rejects_teacher(self, factory, teacher_user):
        request = _make_request(factory, user=teacher_user)
        assert IsAdmin().has_permission(request, _DummyView()) is False

    def test_rejects_anonymous(self, factory):
        request = _make_request(factory, user=AnonymousUser())
        assert IsAdmin().has_permission(request, _DummyView()) is False


@pytest.mark.django_db
class TestIsAdminOrTeacher:
    """IsAdminOrTeacher 权限测试"""

    def test_allows_admin(self, factory, admin_user):
        request = _make_request(factory, user=admin_user)
        assert IsAdminOrTeacher().has_permission(request, _DummyView()) is True

    def test_allows_teacher(self, factory, teacher_user):
        request = _make_request(factory, user=teacher_user)
        assert IsAdminOrTeacher().has_permission(request, _DummyView()) is True

    def test_rejects_student(self, factory, student_user):
        request = _make_request(factory, user=student_user)
        assert IsAdminOrTeacher().has_permission(request, _DummyView()) is False

    def test_rejects_anonymous(self, factory):
        request = _make_request(factory, user=AnonymousUser())
        assert IsAdminOrTeacher().has_permission(request, _DummyView()) is False


@pytest.mark.django_db
class TestIsAdminOrReadOnly:
    """IsAdminOrReadOnly 权限测试"""

    def test_admin_can_write(self, factory, admin_user):
        request = _make_request(factory, method="post", user=admin_user)
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is True

    def test_admin_can_read(self, factory, admin_user):
        request = _make_request(factory, method="get", user=admin_user)
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is True

    def test_student_can_read(self, factory, student_user):
        request = _make_request(factory, method="get", user=student_user)
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is True

    def test_student_cannot_write(self, factory, student_user):
        request = _make_request(factory, method="post", user=student_user)
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is False

    def test_teacher_can_read(self, factory, teacher_user):
        request = _make_request(factory, method="get", user=teacher_user)
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is True

    def test_teacher_cannot_write(self, factory, teacher_user):
        request = _make_request(factory, method="post", user=teacher_user)
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is False

    def test_anonymous_rejected(self, factory):
        request = _make_request(factory, method="get", user=AnonymousUser())
        assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is False

    def test_safe_methods_allowed_for_student(self, factory, student_user):
        """所有 SAFE_METHODS (GET/HEAD/OPTIONS) 对学生可读"""
        for method in ("get", "head", "options"):
            request = _make_request(factory, method=method, user=student_user)
            assert IsAdminOrReadOnly().has_permission(request, _DummyView()) is True


@pytest.mark.django_db
class TestIsOwnerOrReadOnly:
    """IsOwnerOrReadOnly 权限测试（对象级权限）"""

    def test_owner_can_write(self, factory, student_user):
        request = _make_request(factory, method="put", user=student_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwnerOrReadOnly().has_object_permission(
            request, _DummyView(), obj
        ) is True

    def test_non_owner_can_read(self, factory, teacher_user, student_user):
        """非所有者可读"""
        request = _make_request(factory, method="get", user=teacher_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwnerOrReadOnly().has_object_permission(
            request, _DummyView(), obj
        ) is True

    def test_non_owner_cannot_write(self, factory, teacher_user, student_user):
        request = _make_request(factory, method="put", user=teacher_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwnerOrReadOnly().has_object_permission(
            request, _DummyView(), obj
        ) is False

    def test_owner_can_read(self, factory, student_user):
        request = _make_request(factory, method="get", user=student_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwnerOrReadOnly().has_object_permission(
            request, _DummyView(), obj
        ) is True

    def test_object_without_owner_rejected_for_write(self, factory, student_user):
        """对象无 user/student/teacher 字段时，写操作拒绝"""
        request = _make_request(factory, method="put", user=student_user)
        obj = _DummyObject(owner=None)
        # owner 为 None 时，getattr 返回 None，应拒绝写
        assert IsOwnerOrReadOnly().has_object_permission(
            request, _DummyView(), obj
        ) is False

    def test_object_without_owner_allows_read(self, factory, student_user):
        request = _make_request(factory, method="get", user=student_user)
        obj = _DummyObject(owner=None)
        assert IsOwnerOrReadOnly().has_object_permission(
            request, _DummyView(), obj
        ) is True


@pytest.mark.django_db
class TestIsOwner:
    """IsOwner 权限测试（仅所有者，含读）"""

    def test_owner_allowed(self, factory, student_user):
        request = _make_request(factory, method="get", user=student_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwner().has_object_permission(
            request, _DummyView(), obj
        ) is True

    def test_non_owner_rejected_read(self, factory, teacher_user, student_user):
        """非所有者读也拒绝"""
        request = _make_request(factory, method="get", user=teacher_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwner().has_object_permission(
            request, _DummyView(), obj
        ) is False

    def test_non_owner_rejected_write(self, factory, teacher_user, student_user):
        request = _make_request(factory, method="put", user=teacher_user)
        obj = _DummyObject(owner=student_user)
        assert IsOwner().has_object_permission(
            request, _DummyView(), obj
        ) is False

    def test_no_owner_rejected(self, factory, student_user):
        request = _make_request(factory, method="get", user=student_user)
        obj = _DummyObject(owner=None)
        assert IsOwner().has_object_permission(
            request, _DummyView(), obj
        ) is False


@pytest.mark.django_db
class TestHasActiveStatus:
    """HasActiveStatus 权限测试"""

    def test_active_user_allowed(self, factory, student_user):
        request = _make_request(factory, user=student_user)
        assert HasActiveStatus().has_permission(request, _DummyView()) is True

    def test_disabled_user_rejected(self, factory, disabled_user):
        request = _make_request(factory, user=disabled_user)
        assert HasActiveStatus().has_permission(request, _DummyView()) is False

    def test_anonymous_rejected(self, factory):
        request = _make_request(factory, user=AnonymousUser())
        assert HasActiveStatus().has_permission(request, _DummyView()) is False

    def test_admin_active_allowed(self, factory, admin_user):
        request = _make_request(factory, user=admin_user)
        assert HasActiveStatus().has_permission(request, _DummyView()) is True
