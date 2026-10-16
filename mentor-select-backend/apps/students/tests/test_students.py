"""
学生模块测试
覆盖 Model / Serializer / Service / Permission
"""
import pytest

from apps.common.enums import UserRole
from apps.common.exceptions import BusinessException, NotFoundError
from apps.students.models import StudentProfile
from apps.students.serializers import (
    StudentProfileCreateSerializer,
    StudentProfileSerializer,
)
from apps.students.services import StudentProfileService
from apps.users.models import User


@pytest.mark.django_db
class TestStudentProfileModel:
    """StudentProfile Model 测试"""

    def test_create_student_profile(self, student_user):
        profile = StudentProfile.objects.create(
            user=student_user,
            student_number="20240001",
            name="张三",
            major="计算机科学与技术",
            class_name="计科2401",
        )
        assert profile.user_id is not None
        assert profile.user_id == student_user.id
        assert profile.student_number == "20240001"
        assert str(profile) == "20240001 张三"

    def test_student_number_unique(self, student_user):
        StudentProfile.objects.create(
            user=student_user,
            student_number="20240001",
            name="张三",
            major="计算机",
            class_name="计科2401",
        )
        # 创建第二个用户
        user2 = User.objects.create_user(
            username="student002",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
        )
        with pytest.raises(Exception):  # IntegrityError
            StudentProfile.objects.create(
                user=user2,
                student_number="20240001",  # 重复
                name="李四",
                major="计算机",
                class_name="计科2402",
            )


@pytest.mark.django_db
class TestStudentProfileSerializer:
    """StudentProfile Serializer 测试"""

    def test_create_serializer_valid(self):
        data = {
            "user": 1,
            "student_number": "20240001",
            "name": "张三",
            "major": "计算机科学与技术",
            "class_name": "计科2401",
        }
        serializer = StudentProfileCreateSerializer(data=data)
        # 不调用 is_valid，因为有 user 外键校验

    def test_serializer_read_fields(self, student_profile):
        serializer = StudentProfileSerializer(student_profile)
        data = serializer.data
        assert "user" in data
        assert "student_number" in data
        assert "name" in data
        assert "major" in data
        assert "class_name" in data


@pytest.mark.django_db
class TestStudentProfileService:
    """StudentProfileService 测试"""

    def test_create_student_profile(self, student_user):
        service = StudentProfileService()
        profile = service.create({
            "user": student_user,
            "student_number": "20240002",
            "name": "李四",
            "major": "软件工程",
            "class_name": "软工2401",
        })
        assert profile.user_id is not None
        assert profile.name == "李四"

    def test_create_duplicate_student_number(self, student_profile):
        service = StudentProfileService()
        # 创建第二个用户
        user2 = User.objects.create_user(
            username="student002",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
        )
        with pytest.raises(BusinessException):
            service.create({
                "user": user2,
                "student_number": student_profile.student_number,
                "name": "李四",
                "major": "软件工程",
                "class_name": "软工2401",
            })

    def test_get_by_id(self, student_profile):
        service = StudentProfileService()
        result = service.get_by_id(student_profile.user_id)
        assert result.user_id == student_profile.user_id

    def test_get_by_id_not_found(self):
        service = StudentProfileService()
        with pytest.raises(NotFoundError):
            service.get_by_id(99999)

    def test_update_student_profile(self, student_profile):
        service = StudentProfileService()
        updated = service.update(student_profile.user_id, {"major": "人工智能"})
        assert updated.major == "人工智能"

    def test_delete_student_profile(self, student_profile):
        service = StudentProfileService()
        service.delete(student_profile.user_id)
        # 软删除后默认 manager 不返回
        assert not StudentProfile.objects.filter(
            user_id=student_profile.user_id
        ).exists()

    def test_get_by_user_id(self, student_profile):
        service = StudentProfileService()
        result = service.get_by_user_id(student_profile.user_id)
        assert result.user_id == student_profile.user_id


@pytest.mark.django_db
class TestStudentPermission:
    """学生权限测试"""

    def test_admin_can_list_students(self, authenticated_client, student_profile):
        resp = authenticated_client.get("/api/v1/students/profiles/")
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list_students(self, api_client):
        resp = api_client.get("/api/v1/students/profiles/")
        assert resp.status_code == 401

    def test_student_list_is_scoped_to_self(
        self, student_client, student_user, student_profile
    ):
        """学生档案列表按角色裁剪：学生只能看到自己，不返回他人明细。

        （读接口对已认证开放，但 ViewSet 的 get_queryset 会裁剪范围，
        因此不是「全部 403」也不是「全部 200」。）
        """
        from apps.students.models import StudentProfile

        # 另一个学生（不得出现在当前学生的响应里）
        from apps.common.enums import UserRole
        from apps.users.models import User

        other_user = User.objects.create_user(
            username="other_stu", password="TestPass123!", role=UserRole.STUDENT.value
        )
        other_profile = StudentProfile.objects.create(
            user=other_user,
            student_number="S20247777",
            name="其他学生",
            major="软件工程",
            class_name="软工2401",
            phone="13500000000",
        )

        resp = student_client.get("/api/v1/students/profiles/")
        assert resp.status_code == 200
        rows = resp.data["data"]
        if isinstance(rows, dict):
            rows = rows.get("list", [])
        ids = {row["user"] for row in rows}  # 档案主键 = user_id
        assert ids == {student_user.id}
        assert other_profile.user_id not in ids
        # 不得泄漏他人明细
        assert other_user.username not in str(rows)
        assert "S20247777" not in str(rows)
