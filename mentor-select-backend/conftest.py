"""
pytest 全局 fixtures
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.academic_year.models import AcademicYear
from apps.common.enums import (
    AcademicYearStatus,
    UserRole,
    UserStatus,
)
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile
from apps.users.models import User


@pytest.fixture
def api_client():
    """DRF API 测试客户端"""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """管理员用户"""
    return User.objects.create_user(
        username="admin001",
        password="TestPass123!",
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def teacher_user(db):
    """导师用户"""
    return User.objects.create_user(
        username="teacher001",
        password="TestPass123!",
        role=UserRole.TEACHER.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def student_user(db):
    """学生用户"""
    return User.objects.create_user(
        username="student001",
        password="TestPass123!",
        role=UserRole.STUDENT.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def teacher_profile(db, teacher_user):
    """导师档案"""
    return TeacherProfile.objects.create(
        user=teacher_user,
        teacher_number="T0001",
        name="测试导师",
        college="计算机学院",
        research_area="人工智能",
    )


@pytest.fixture
def student_profile(db, student_user):
    """学生档案"""
    return StudentProfile.objects.create(
        user=student_user,
        student_number="20240001",
        name="测试学生",
        major="计算机科学与技术",
        class_name="计科2401",
    )


@pytest.fixture
def academic_year(db):
    """学年"""
    return AcademicYear.objects.create(
        name="2024-2025",
        start_year=2024,
        end_year=2025,
        status=AcademicYearStatus.ACTIVE.value,
    )


@pytest.fixture
def authenticated_client(api_client, admin_user):
    """已认证的管理员 API 客户端"""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def teacher_client(api_client, teacher_user):
    """已认证的导师 API 客户端"""
    refresh = RefreshToken.for_user(teacher_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def student_client(api_client, student_user):
    """已认证的学生 API 客户端"""
    refresh = RefreshToken.for_user(student_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def celery_eager(db):
    """Celery eager 模式（同步执行任务）

    在测试中使用 eager 模式，避免依赖真实 Celery worker。
    """
    from celery import current_app

    old_config = {
        "task_always_eager": current_app.conf.task_always_eager,
        "task_eager_propagates": current_app.conf.task_eager_propagates,
    }
    current_app.conf.task_always_eager = True
    current_app.conf.task_eager_propagates = True
    try:
        yield
    finally:
        current_app.conf.task_always_eager = old_config["task_always_eager"]
        current_app.conf.task_eager_propagates = old_config["task_eager_propagates"]
