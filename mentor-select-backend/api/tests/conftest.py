"""api 测试公共 fixtures（canonical，2026-10-16 重写）

变更说明（旧的 legacy 测试夹具已废弃）：
- 旧实现覆盖 pytest-django 的 `django_db_setup`，DROP 掉 canonical `user` 表并按
  legacy 7 列表结构重建，再手工 CREATE legacy `student`/`teacher`/`admin` 表。
  该做法会让整套测试运行在非 Migration 产生的 schema 上，且会破坏
  pytest-django 根 fixtures（同名覆盖）。
- 新实现完全使用 Django Migration 建立的 canonical 表
  （`apps.users.User` / `StudentProfile` / `TeacherProfile` / `AdminProfile`），
  不 DROP、不重建、不触碰任何真实表。
- canonical 档案主键 = user_id，测试中的 "student_id"/"teacher_id" 即 user_id。
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.enums import UserRole, UserStatus
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile
from apps.users.models import AdminProfile, User


def _create_user(username: str, password: str, role: int) -> User:
    """创建 canonical 用户（密码走 Django canonical hashing）"""
    return User.objects.create_user(
        username=username,
        password=password,
        role=role,
        status=int(UserStatus.ACTIVE),
    )


@pytest.fixture
def api_admin_user(db) -> User:
    """测试用管理员用户（canonical apps.users.User）

    命名刻意避开根 conftest 的 `admin_user`，避免覆盖根 fixtures。
    """
    return _create_user("test_admin", "Admin12345", int(UserRole.ADMIN))


@pytest.fixture
def api_client(api_admin_user) -> APIClient:
    """DRF API 测试客户端（默认以管理员身份认证）

    v2 写操作接口要求 IsAdmin，读接口要求 IsAuthenticated；
    默认以管理员身份认证可覆盖两类场景，公开接口（login）不受影响。
    """
    client = APIClient()
    client.force_authenticate(user=api_admin_user)
    return client


@pytest.fixture
def anonymous_client() -> APIClient:
    """未认证的 API 客户端"""
    return APIClient()


@pytest.fixture
def jwt_client():
    """按 canonical User 生成带 v1 JWT（SimpleJWT access token）的 APIClient

    v1 登录接口（apps.users.services.AuthService.login）签发的就是同一类 token，
    因此该 fixture 用于验证「v1 JWT 可以认证 v2 canonical 接口」。
    """

    def _make(user: User) -> APIClient:
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    return _make


@pytest.fixture
def api_teacher_user(db) -> User:
    """测试用导师用户（canonical）"""
    return _create_user("test_teacher", "Teacher12345", int(UserRole.TEACHER))


@pytest.fixture
def api_teacher_profile(db, api_teacher_user) -> TeacherProfile:
    """导师档案（canonical，主键 = user_id）"""
    return TeacherProfile.objects.create(
        user=api_teacher_user,
        teacher_number="T0001",
        name="测试导师",
        college="计算机学院",
    )


@pytest.fixture
def api_student_user(db) -> User:
    """测试用学生用户（canonical）"""
    return _create_user("test_student", "Student12345", int(UserRole.STUDENT))


@pytest.fixture
def api_student_profile(db, api_student_user) -> StudentProfile:
    """学生档案（canonical，主键 = user_id）"""
    return StudentProfile.objects.create(
        user=api_student_user,
        student_number="S20249999",
        name="测试学生",
        major="计算机科学",
        class_name="计科2401",
        phone="13700000000",
    )


@pytest.fixture
def api_admin_profile(db, api_admin_user) -> AdminProfile:
    """管理员档案（canonical，主键 = user_id）"""
    return AdminProfile.objects.create(user=api_admin_user, name="测试管理员")
