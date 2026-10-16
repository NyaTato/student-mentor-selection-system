"""v2 学生接口「整条记录」角色裁剪测试（最终评审收紧项）

覆盖 4 个读取变体：
- GET /api/v2/students/{student_id}
- GET /api/v2/students/by_user/{user_id}
- GET /api/v2/students/by_number/{student_number}
- GET /api/v2/students/list

期望（review-checkpoints.md 最终评审要求）：
- 匿名：401（IsAuthenticated）
- 学生：仅本人可见（他人 → 404；list 只含自己）
- 导师：仅「与自己存在真实申请或录取关系」的学生可见（无关学生 → 404；list 为空）
- 管理员：全部可见
- 未授权记录一律 404，且**不计入分页 total**（裁剪发生在 queryset 层）
- phone 随整条记录一起可见/不可见（不再「看得到记录但 phone=null」）
"""
import pytest
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
    UserStatus,
)
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile
from apps.users.models import User


def _make_user(username: str, role: int) -> User:
    return User.objects.create_user(
        username=username,
        password="TestPass123!",
        role=role,
        status=UserStatus.ACTIVE.value,
    )


def _make_student(username: str, number: str, name: str, phone: str) -> StudentProfile:
    user = _make_user(username, UserRole.STUDENT.value)
    return StudentProfile.objects.create(
        user=user,
        student_number=number,
        name=name,
        major="计算机科学",
        class_name="计科2401",
        phone=phone,
    )


def _make_teacher(username: str, number: str) -> TeacherProfile:
    user = _make_user(username, UserRole.TEACHER.value)
    return TeacherProfile.objects.create(
        user=user,
        teacher_number=number,
        name=f"导师{number}",
        college="计算机学院",
    )


def _client_for(user: User) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def scope_data(db):
    """三名学生 + 一名「有关系」导师 + 一名「无关系」导师"""
    stu_a = _make_student("scope_stu_a", "SCOPEA001", "学生A", "13000000001")
    stu_b = _make_student("scope_stu_b", "SCOPEB001", "学生B", "13000000002")
    stu_c = _make_student("scope_stu_c", "SCOPEC001", "学生C", "13000000003")

    related_teacher = _make_teacher("scope_teacher_rel", "ST001")
    unrelated_teacher = _make_teacher("scope_teacher_unrel", "ST002")

    year = AcademicYear.objects.create(
        name="2030-2031", start_year=2030, end_year=2031,
        status=AcademicYearStatus.ACTIVE.value,
    )
    # 学生A -> 有关系导师（真实申请）
    Application.objects.create(
        academic_year=year, student=stu_a, teacher=related_teacher,
        round=ApplicationRound.FIRST_ROUND.value,
    )
    return {
        "students": [stu_a, stu_b, stu_c],
        "stu_a": stu_a, "stu_b": stu_b, "stu_c": stu_c,
        "related_teacher": related_teacher,
        "unrelated_teacher": unrelated_teacher,
        "year": year,
    }


# --- 匿名 ---------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_denied_on_all_read_variants(scope_data):
    """匿名访问四个读取变体全部被拒（401）"""
    client = APIClient()  # 未认证
    stu_a = scope_data["stu_a"]
    assert client.get(f"/api/v2/students/{stu_a.pk}").status_code == 401
    assert client.get(f"/api/v2/students/by_user/{stu_a.user_id}").status_code == 401
    assert client.get(f"/api/v2/students/by_number/{stu_a.student_number}").status_code == 401
    assert client.get("/api/v2/students/list").status_code == 401


# --- 学生 ---------------------------------------------------------------


@pytest.mark.django_db
def test_student_can_read_self_via_all_variants(scope_data):
    """学生本人：detail / by_user / by_number 均 200，且 phone 可见"""
    stu_a = scope_data["stu_a"]
    client = _client_for(stu_a.user)

    by_id = client.get(f"/api/v2/students/{stu_a.pk}")
    assert by_id.status_code == 200
    assert by_id.json()["data"]["student_number"] == "SCOPEA001"
    assert by_id.json()["data"]["phone"] == "13000000001"

    by_user = client.get(f"/api/v2/students/by_user/{stu_a.user_id}")
    assert by_user.status_code == 200
    assert by_user.json()["data"]["name"] == "学生A"
    assert by_user.json()["data"]["phone"] == "13000000001"

    by_number = client.get(f"/api/v2/students/by_number/SCOPEA001")
    assert by_number.status_code == 200
    assert by_number.json()["data"]["id"] == stu_a.pk
    assert by_number.json()["data"]["phone"] == "13000000001"


@pytest.mark.django_db
def test_student_list_contains_only_self_and_total_is_one(scope_data):
    """学生 list：只含自己，total=1（未授权记录不泄露且不计入总数）"""
    stu_a = scope_data["stu_a"]
    client = _client_for(stu_a.user)

    resp = client.get("/api/v2/students/list?page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert [row["id"] for row in data["list"]] == [stu_a.pk]
    assert data["list"][0]["phone"] == "13000000001"


@pytest.mark.django_db
def test_student_cannot_read_other_student_via_any_variant(scope_data):
    """学生读他人：detail / by_user / by_number 全部 404（而非返回 phone=null）"""
    stu_a = scope_data["stu_a"]
    stu_b = scope_data["stu_b"]
    client = _client_for(stu_a.user)

    assert client.get(f"/api/v2/students/{stu_b.pk}").status_code == 404
    assert client.get(f"/api/v2/students/by_user/{stu_b.user_id}").status_code == 404
    assert client.get(f"/api/v2/students/by_number/{stu_b.student_number}").status_code == 404


# --- 导师 ---------------------------------------------------------------


@pytest.mark.django_db
def test_unrelated_teacher_sees_no_records_on_all_variants(scope_data):
    """无关导师：三个详情变体 404，list 为空且 total=0"""
    teacher = scope_data["unrelated_teacher"]
    stu_a = scope_data["stu_a"]
    client = _client_for(teacher.user)

    assert client.get(f"/api/v2/students/{stu_a.pk}").status_code == 404
    assert client.get(f"/api/v2/students/by_user/{stu_a.user_id}").status_code == 404
    assert client.get(f"/api/v2/students/by_number/{stu_a.student_number}").status_code == 404

    resp = client.get("/api/v2/students/list?page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0
    assert data["list"] == []


@pytest.mark.django_db
def test_related_teacher_sees_applicant_on_all_variants(scope_data):
    """有关系导师（真实申请）：三个详情变体 200 且 phone 可见，list 仅含申请人"""
    teacher = scope_data["related_teacher"]
    stu_a = scope_data["stu_a"]
    client = _client_for(teacher.user)

    by_id = client.get(f"/api/v2/students/{stu_a.pk}")
    assert by_id.status_code == 200
    assert by_id.json()["data"]["phone"] == "13000000001"

    assert client.get(f"/api/v2/students/by_user/{stu_a.user_id}").status_code == 200
    assert client.get(f"/api/v2/students/by_number/SCOPEA001").status_code == 200

    resp = client.get("/api/v2/students/list?page=1&page_size=20")
    data = resp.json()["data"]
    assert data["total"] == 1
    assert [row["id"] for row in data["list"]] == [stu_a.pk]


@pytest.mark.django_db
def test_related_teacher_pagination_total_excludes_unauthorized_rows(scope_data):
    """分页 total 只统计授权行：3 名学生中导师只与 1 名有关系 → total=1"""
    teacher = scope_data["related_teacher"]
    stu_b = scope_data["stu_b"]
    client = _client_for(teacher.user)

    resp = client.get("/api/v2/students/list?page=1&page_size=2")
    data = resp.json()["data"]
    assert data["total"] == 1
    assert len(data["list"]) == 1

    # 第二页为空，且 total 不变（裁剪在 COUNT 之前）
    assert data["list"][0]["id"] != stu_b.pk
    page2 = client.get("/api/v2/students/list?page=2&page_size=2").json()["data"]
    assert page2["total"] == 1
    assert page2["list"] == []


@pytest.mark.django_db
def test_admission_relationship_grants_access(scope_data):
    """录取关系（无申请）同样授予整条记录可见性"""
    teacher = scope_data["related_teacher"]
    stu_c = scope_data["stu_c"]
    client = _client_for(teacher.user)

    assert client.get(f"/api/v2/students/{stu_c.pk}").status_code == 404

    Admission.objects.create(
        academic_year=scope_data["year"], student=stu_c, teacher=teacher,
        source=AdmissionSource.MANUAL.value,
    )
    assert client.get(f"/api/v2/students/{stu_c.pk}").status_code == 200
    assert client.get(f"/api/v2/students/by_number/SCOPEC001").status_code == 200


@pytest.mark.django_db
def test_other_teachers_admission_does_not_grant_access(scope_data):
    """别的导师产生的录取关系不会让本导师获得访问权"""
    other = scope_data["unrelated_teacher"]
    stu_c = scope_data["stu_c"]
    Admission.objects.create(
        academic_year=scope_data["year"], student=stu_c,
        teacher=scope_data["related_teacher"], source=AdmissionSource.MANUAL.value,
    )
    client = _client_for(other.user)
    assert client.get(f"/api/v2/students/{stu_c.pk}").status_code == 404
    assert client.get("/api/v2/students/list").json()["data"]["total"] == 0


# --- 管理员 -------------------------------------------------------------


@pytest.mark.django_db
def test_admin_sees_all_students_on_all_variants(scope_data):
    """管理员：四个变体全部可见（total = 全部人数），phone 可见"""
    admin = _make_user("scope_admin", UserRole.ADMIN.value)
    client = _client_for(admin)
    stu_a, stu_b, stu_c = scope_data["students"]

    for profile in (stu_a, stu_b, stu_c):
        assert client.get(f"/api/v2/students/{profile.pk}").status_code == 200
        assert client.get(f"/api/v2/students/by_user/{profile.user_id}").status_code == 200
        assert (
            client.get(f"/api/v2/students/by_number/{profile.student_number}").status_code
            == 200
        )

    resp = client.get("/api/v2/students/list?page=1&page_size=20")
    data = resp.json()["data"]
    assert data["total"] == 3
    assert {row["id"] for row in data["list"]} == {stu_a.pk, stu_b.pk, stu_c.pk}
    assert all(row["phone"] for row in data["list"])
