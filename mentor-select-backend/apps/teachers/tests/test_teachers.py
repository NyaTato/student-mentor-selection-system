"""
导师模块测试
覆盖 Model / Serializer / Service / Permission
"""
import pytest

from apps.common.enums import AcademicYearStatus, UserRole
from apps.common.exceptions import BusinessException, NotFoundError
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.teachers.services import TeacherProfileService, TeacherQuotaService
from apps.users.models import User


@pytest.mark.django_db
class TestTeacherProfileModel:
    """TeacherProfile Model 测试"""

    def test_create_teacher_profile(self, teacher_user):
        profile = TeacherProfile.objects.create(
            user=teacher_user,
            teacher_number="T0001",
            name="王教授",
            college="计算机学院",
            research_area="人工智能",
        )
        assert profile.user_id == teacher_user.id
        assert profile.teacher_number == "T0001"
        assert "T0001" in str(profile)

    def test_teacher_number_unique(self, teacher_user):
        TeacherProfile.objects.create(
            user=teacher_user,
            teacher_number="T0001",
            name="王教授",
            college="计算机学院",
        )
        user2 = User.objects.create_user(
            username="teacher002",
            password="TestPass123!",
            role=UserRole.TEACHER.value,
        )
        with pytest.raises(Exception):  # IntegrityError
            TeacherProfile.objects.create(
                user=user2,
                teacher_number="T0001",
                name="李教授",
                college="计算机学院",
            )


@pytest.mark.django_db
class TestTeacherQuotaModel:
    """TeacherQuota Model 测试"""

    def test_create_quota(self, teacher_profile, academic_year):
        quota = TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=5,
        )
        assert quota.max_quota == 5
        assert quota.academic_year_id == academic_year.id

    def test_quota_unique_per_year_teacher(self, teacher_profile, academic_year):
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=5,
        )
        with pytest.raises(Exception):  # IntegrityError
            TeacherQuota.objects.create(
                academic_year=academic_year,
                teacher=teacher_profile,
                max_quota=3,
            )


@pytest.mark.django_db
class TestTeacherProfileService:
    """TeacherProfileService 测试"""

    def test_create_teacher_profile(self, teacher_user):
        service = TeacherProfileService()
        profile = service.create({
            "user": teacher_user,
            "teacher_number": "T0002",
            "name": "张教授",
            "college": "软件学院",
        })
        assert profile.user_id is not None
        assert profile.name == "张教授"

    def test_create_duplicate_teacher_number(self, teacher_profile):
        service = TeacherProfileService()
        user2 = User.objects.create_user(
            username="teacher002",
            password="TestPass123!",
            role=UserRole.TEACHER.value,
        )
        with pytest.raises(BusinessException):
            service.create({
                "user": user2,
                "teacher_number": teacher_profile.teacher_number,
                "name": "李教授",
                "college": "软件学院",
            })

    def test_get_by_id(self, teacher_profile):
        service = TeacherProfileService()
        result = service.get_by_id(teacher_profile.user_id)
        assert result.user_id == teacher_profile.user_id

    def test_get_by_id_not_found(self):
        service = TeacherProfileService()
        with pytest.raises(NotFoundError):
            service.get_by_id(99999)

    def test_get_by_user_id(self, teacher_profile):
        service = TeacherProfileService()
        result = service.get_by_user_id(teacher_profile.user_id)
        assert result.user_id == teacher_profile.user_id

    def test_update_teacher_profile(self, teacher_profile):
        service = TeacherProfileService()
        updated = service.update(teacher_profile.user_id, {"college": "电子学院"})
        assert updated.college == "电子学院"

    def test_delete_teacher_profile(self, teacher_profile):
        service = TeacherProfileService()
        service.delete(teacher_profile.user_id)
        assert not TeacherProfile.objects.filter(
            user_id=teacher_profile.user_id
        ).exists()


@pytest.mark.django_db
class TestTeacherQuotaService:
    """TeacherQuotaService 测试"""

    def test_create_quota(self, teacher_profile, academic_year):
        service = TeacherQuotaService()
        quota = service.create({
            "academic_year": academic_year,
            "teacher": teacher_profile,
            "max_quota": 5,
        })
        assert quota.id is not None
        assert quota.max_quota == 5

    def test_get_by_year_and_teacher(self, teacher_profile, academic_year):
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=3,
        )
        service = TeacherQuotaService()
        quota = service.get_by_year_and_teacher(academic_year.id, teacher_profile.user_id)
        assert quota is not None
        assert quota.max_quota == 3

    def test_list_by_year(self, teacher_profile, academic_year):
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=3,
        )
        service = TeacherQuotaService()
        quotas = service.list_by_year(academic_year.id)
        assert quotas.count() == 1

    def test_batch_set_quota(self, teacher_profile, academic_year):
        # 创建第二个导师
        user2 = User.objects.create_user(
            username="teacher002",
            password="TestPass123!",
            role=UserRole.TEACHER.value,
        )
        teacher2 = TeacherProfile.objects.create(
            user=user2,
            teacher_number="T0002",
            name="李教授",
            college="计算机学院",
        )
        service = TeacherQuotaService()
        instances = service.batch_set_quota(
            academic_year_id=academic_year.id,
            quotas=[
                {"teacher_id": teacher_profile.user_id, "max_quota": 5},
                {"teacher_id": teacher2.user_id, "max_quota": 3},
            ],
        )
        assert len(instances) == 2

    def test_batch_set_quota_update_existing(self, teacher_profile, academic_year):
        """批量设置已存在的名额会更新"""
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=1,
        )
        service = TeacherQuotaService()
        instances = service.batch_set_quota(
            academic_year_id=academic_year.id,
            quotas=[
                {"teacher_id": teacher_profile.user_id, "max_quota": 10},
            ],
        )
        assert len(instances) == 1
        assert instances[0].max_quota == 10


@pytest.mark.django_db
class TestTeacherPermission:
    """导师权限测试"""

    def test_admin_can_list_teachers(self, authenticated_client, teacher_profile):
        resp = authenticated_client.get("/api/v1/teachers/profiles/")
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list_teachers(self, api_client):
        resp = api_client.get("/api/v1/teachers/profiles/")
        assert resp.status_code == 401

    def test_teacher_can_access_me(self, teacher_client, teacher_profile):
        resp = teacher_client.get("/api/v1/teachers/profiles/me/")
        assert resp.status_code == 200

    def test_student_cannot_access_teacher_me(self, student_client):
        resp = student_client.get("/api/v1/teachers/profiles/me/")
        assert resp.status_code == 403
