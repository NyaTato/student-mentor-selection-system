"""canonical v2 集成与安全回归测试（本任务新增）

覆盖目标：
1. v2 CRUD 只写 canonical apps models，测试库中不存在 legacy 表
2. v1 登录逻辑签发的 JWT 可以认证 v2 canonical 接口
3. canonical applications / students/profile 互为同一份数据（无需 legacy 表）
4. 学生手机号字段级权限：本人 / 管理员 / 有真实申请或录取关系的导师
5. 管理员档案查询接口仅管理员可访问

ID 契约：canonical profile 主键 = user_id，因此 v2 响应 id == user_id。
"""
import pytest
from django.contrib.auth.hashers import check_password
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.academic_year.models import AcademicYear
from apps.applications.models import Application
from apps.assignments.models import Admission
from apps.common.enums import (
    AcademicYearStatus,
    AdmissionSource,
    ApplicationRound,
    UserRole,
)
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile
from apps.users.models import User
from apps.users.services import AuthService


def _jwt_client(access_token: str) -> APIClient:
    """用给定 access token 构造 API 客户端"""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


def _create_student_via_v2(api_client, username: str, number: str, phone: str) -> dict:
    """通过 v2 API 创建学生，返回响应 data"""
    response = api_client.post(
        "/api/v2/students/create",
        {
            "username": username,
            "password": "ValidPass123",
            "student_number": number,
            "name": f"姓名{username}",
            "major": "计算机科学",
            "class_name": "计科2401",
            "phone": phone,
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    return response.json()["data"]


@pytest.mark.django_db
def test_v2_crud_writes_canonical_models_and_accepts_v1_jwt(api_client):
    """v2 CRUD → canonical 表；v1 登录签发的 JWT 可认证 v2 接口"""
    data = _create_student_via_v2(api_client, "canon01", "CANON00001", "13800001111")

    # ID 契约：student_id 与 user_id 都是 canonical user_id
    user_id = data["user_id"]
    assert data["student_id"] == user_id

    profile = StudentProfile.objects.get(pk=user_id)
    assert profile.user_id == user_id
    assert profile.phone == "13800001111"

    user = User.objects.get(pk=user_id)
    assert user.role == int(UserRole.STUDENT)
    # canonical Django password hashing
    assert check_password("ValidPass123", user.password)

    # 测试库中没有 legacy 表（v2 不依赖 legacy profile 表）
    existing_tables = set(connection.introspection.table_names())
    assert "student_profile" in existing_tables
    assert "student" not in existing_tables
    assert "teacher" not in existing_tables
    assert "admin" not in existing_tables

    # v1 登录逻辑签发的 JWT（POST /api/v1/auth/login/ 走的就是 AuthService.login）
    login_result = AuthService.login("canon01", "ValidPass123")
    student_client = _jwt_client(login_result["access"])

    detail = student_client.get(f"/api/v2/students/{user_id}")
    assert detail.status_code == 200
    payload = detail.json()["data"]
    assert payload["id"] == user_id
    assert payload["user_id"] == user_id
    assert payload["student_number"] == "CANON00001"
    # 本人可见自己的手机号
    assert payload["phone"] == "13800001111"


@pytest.mark.django_db
def test_application_and_profile_read_same_canonical_row(api_client):
    """canonical application 与 v2 学生档案指向同一行数据（无 legacy 表）"""
    student_data = _create_student_via_v2(api_client, "canon02", "CANON00002", "13800002222")
    student_user_id = student_data["user_id"]

    teacher_response = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "canonteacher",
            "password": "ValidPass123",
            "teacher_number": "TCANON0001",
            "name": "导师甲",
            "college": "计算机学院",
        },
        format="json",
    )
    assert teacher_response.status_code == 200, teacher_response.content
    teacher_user_id = teacher_response.json()["data"]["teacher_id"]

    academic_year = AcademicYear.objects.create(
        name="2024-2025",
        start_year=2024,
        end_year=2025,
        status=int(AcademicYearStatus.ACTIVE),
    )
    application = Application.objects.create(
        academic_year=academic_year,
        student=StudentProfile.objects.get(pk=student_user_id),
        teacher=TeacherProfile.objects.get(pk=teacher_user_id),
        round=int(ApplicationRound.FIRST_ROUND),
    )

    # FK 落地在 canonical user_id 上，与 v2 响应 id 完全一致
    assert application.student_id == student_user_id
    assert application.teacher_id == teacher_user_id

    detail = api_client.get(f"/api/v2/students/{student_user_id}")
    assert detail.json()["data"]["name"] == application.student.name


@pytest.mark.django_db
def test_student_phone_field_level_permissions(
    api_client, api_teacher_user, api_teacher_profile, api_student_user, api_student_profile
):
    """整条学生记录（含 phone）仅本人 / 管理员 / 有真实申请或录取关系的导师可见

    最终评审收紧：未授权方不再返回「记录但 phone=null」，而是 404。
    """
    student_id = api_student_profile.pk

    # 管理员可见
    admin_view = api_client.get(f"/api/v2/students/{student_id}")
    assert admin_view.json()["data"]["phone"] == "13700000000"

    # 本人可见
    self_client = _jwt_client(str(RefreshToken.for_user(api_student_user).access_token))
    self_view = self_client.get(f"/api/v2/students/{student_id}")
    assert self_view.json()["data"]["phone"] == "13700000000"

    # 无申请/录取关系的导师：整条记录不可见（404）
    teacher_client = _jwt_client(str(RefreshToken.for_user(api_teacher_user).access_token))
    teacher_view = teacher_client.get(f"/api/v2/students/{student_id}")
    assert teacher_view.status_code == 404

    # 导师目录（公开目录）对已认证用户仍开放
    directory = teacher_client.get("/api/v2/teachers/list?page=1&page_size=10")
    assert directory.status_code == 200

    # 建立真实申请关系后，该导师可见整条记录（含 phone）
    academic_year = AcademicYear.objects.create(
        name="2023-2024",
        start_year=2023,
        end_year=2024,
        status=int(AcademicYearStatus.ACTIVE),
    )
    Application.objects.create(
        academic_year=academic_year,
        student=api_student_profile,
        teacher=api_teacher_profile,
        round=int(ApplicationRound.FIRST_ROUND),
    )
    related_view = teacher_client.get(f"/api/v2/students/{student_id}")
    assert related_view.status_code == 200
    assert related_view.json()["data"]["phone"] == "13700000000"

    # 另一个无关系的导师仍不可见（404）
    other_teacher = User.objects.create_user(
        username="other_teacher",
        password="Teacher12345",
        role=int(UserRole.TEACHER),
    )
    TeacherProfile.objects.create(
        user=other_teacher,
        teacher_number="T0002",
        name="无关导师",
        college="外国语学院",
    )
    other_client = _jwt_client(str(RefreshToken.for_user(other_teacher).access_token))
    other_view = other_client.get(f"/api/v2/students/{student_id}")
    assert other_view.status_code == 404

    # 录取关系同样授予可见性
    Admission.objects.create(
        academic_year=academic_year,
        student=api_student_profile,
        teacher=api_teacher_profile,
        source=int(AdmissionSource.MANUAL),
    )
    assert (
        teacher_client.get(f"/api/v2/students/{student_id}").json()["data"]["phone"]
        == "13700000000"
    )


@pytest.mark.django_db
def test_admin_profile_endpoints_require_admin(api_client, api_teacher_user, api_admin_user, api_admin_profile):
    """管理员档案查询仅管理员可访问"""
    teacher_client = _jwt_client(str(RefreshToken.for_user(api_teacher_user).access_token))

    assert teacher_client.get("/api/v2/admins/list?page=1&page_size=10").status_code == 403
    assert teacher_client.get(f"/api/v2/admins/{api_admin_user.pk}").status_code == 403
    assert (
        teacher_client.get(f"/api/v2/admins/by_user/{api_admin_user.pk}").status_code == 403
    )

    # 管理员自身可访问
    assert api_client.get("/api/v2/admins/list?page=1&page_size=10").status_code == 200
    assert api_client.get(f"/api/v2/admins/{api_admin_user.pk}").status_code == 200
