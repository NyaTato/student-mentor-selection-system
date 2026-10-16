"""
学年模块测试
覆盖 Model / Serializer / Service / Permission
"""
import pytest

from apps.academic_year.models import AcademicYear
from apps.academic_year.services import AcademicYearService
from apps.common.enums import AcademicYearStatus
from apps.common.exceptions import BusinessException, NotFoundError, ValidationError


@pytest.mark.django_db
class TestAcademicYearModel:
    """AcademicYear Model 测试"""

    def test_create_academic_year(self):
        year = AcademicYear.objects.create(
            name="2024-2025",
            start_year=2024,
            end_year=2025,
        )
        assert year.id is not None
        assert year.name == "2024-2025"
        assert year.status == AcademicYearStatus.INACTIVE.value
        assert str(year) == "2024-2025"

    def test_name_unique(self):
        AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        with pytest.raises(Exception):  # IntegrityError
            AcademicYear.objects.create(
                name="2024-2025", start_year=2024, end_year=2025
            )


@pytest.mark.django_db
class TestAcademicYearService:
    """AcademicYearService 测试"""

    def test_create_academic_year(self):
        service = AcademicYearService()
        year = service.create({
            "name": "2024-2025",
            "start_year": 2024,
            "end_year": 2025,
        })
        assert year.id is not None
        assert year.name == "2024-2025"

    def test_create_duplicate_name(self):
        AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        with pytest.raises(BusinessException):
            service.create({
                "name": "2024-2025",
                "start_year": 2024,
                "end_year": 2025,
            })

    def test_create_invalid_year_range(self):
        service = AcademicYearService()
        with pytest.raises(ValidationError):
            service.create({
                "name": "2025-2024",
                "start_year": 2025,
                "end_year": 2024,
            })

    def test_get_by_id(self):
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        result = service.get_by_id(year.id)
        assert result.id == year.id

    def test_get_by_id_not_found(self):
        service = AcademicYearService()
        with pytest.raises(NotFoundError):
            service.get_by_id(99999)

    def test_update_academic_year(self):
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        updated = service.update(year.id, {"name": "2024-2026"})
        # name 格式校验会在 serializer 层，service 层只校验唯一
        assert updated.name == "2024-2026"

    def test_update_forbid_status_change(self):
        """不允许通过 update 直接修改 status"""
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        with pytest.raises(ValidationError):
            service.update(year.id, {"status": AcademicYearStatus.ACTIVE.value})

    def test_activate_academic_year(self):
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        activated = service.activate(year.id)
        assert activated.status == AcademicYearStatus.ACTIVE.value
        assert activated.activated_at is not None

    def test_activate_already_active(self):
        year = AcademicYear.objects.create(
            name="2024-2025",
            start_year=2024,
            end_year=2025,
            status=AcademicYearStatus.ACTIVE.value,
        )
        service = AcademicYearService()
        with pytest.raises(BusinessException):
            service.activate(year.id)

    def test_activate_archived_year(self):
        year = AcademicYear.objects.create(
            name="2024-2025",
            start_year=2024,
            end_year=2025,
            status=AcademicYearStatus.ARCHIVED.value,
        )
        service = AcademicYearService()
        with pytest.raises(BusinessException):
            service.activate(year.id)

    def test_activate_archives_previous_active(self):
        """激活新学年时自动归档当前激活的学年"""
        old = AcademicYear.objects.create(
            name="2023-2024",
            start_year=2023,
            end_year=2024,
            status=AcademicYearStatus.ACTIVE.value,
        )
        new = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        service.activate(new.id)

        old.refresh_from_db()
        new.refresh_from_db()
        assert old.status == AcademicYearStatus.ARCHIVED.value
        assert new.status == AcademicYearStatus.ACTIVE.value

    def test_close_academic_year(self):
        year = AcademicYear.objects.create(
            name="2024-2025",
            start_year=2024,
            end_year=2025,
            status=AcademicYearStatus.ACTIVE.value,
        )
        service = AcademicYearService()
        closed = service.close(year.id)
        assert closed.status == AcademicYearStatus.ARCHIVED.value
        assert closed.closed_at is not None

    def test_close_inactive_year(self):
        """非激活的学年不能关闭"""
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        with pytest.raises(BusinessException):
            service.close(year.id)

    def test_delete_active_year_forbidden(self):
        """激活中的学年不允许删除"""
        year = AcademicYear.objects.create(
            name="2024-2025",
            start_year=2024,
            end_year=2025,
            status=AcademicYearStatus.ACTIVE.value,
        )
        service = AcademicYearService()
        with pytest.raises(BusinessException):
            service.delete(year.id)

    def test_delete_inactive_year(self):
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        service = AcademicYearService()
        service.delete(year.id)
        assert not AcademicYear.objects.filter(id=year.id).exists()

    def test_get_active(self):
        year = AcademicYear.objects.create(
            name="2024-2025",
            start_year=2024,
            end_year=2025,
            status=AcademicYearStatus.ACTIVE.value,
        )
        service = AcademicYearService()
        active = service.get_active()
        assert active is not None
        assert active.id == year.id

    def test_get_active_none(self):
        service = AcademicYearService()
        assert service.get_active() is None


@pytest.mark.django_db
class TestAcademicYearPermission:
    """学年权限测试"""

    def test_admin_can_list_years(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/academic-years/")
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list_years(self, api_client):
        resp = api_client.get("/api/v1/academic-years/")
        assert resp.status_code == 401

    def test_student_can_read_years_but_cannot_write(
        self, student_client, academic_year
    ):
        """学年读契约（Task 02 有意收紧写、开放读）：

        已认证用户可读学年目录（选导师 / 选课需要知道当前学年），
        写操作（create/update/destroy/activate/close）仍为管理员专属。
        """
        resp = student_client.get("/api/v1/academic-years/")
        assert resp.status_code == 200
        rows = resp.data["data"]
        if isinstance(rows, dict):  # 分页响应 {list, total, ...}
            rows = rows.get("list", [])
        assert len(rows) >= 1
        # 文档化字段
        for field in (
            "id",
            "name",
            "start_year",
            "end_year",
            "status",
            "status_display",
        ):
            assert field in rows[0]

        resp = student_client.post(
            "/api/v1/academic-years/",
            {"name": "2030-2031", "start_year": 2030, "end_year": 2031},
            format="json",
        )
        assert resp.status_code == 403

    def test_admin_can_create_year(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/v1/academic-years/",
            {"name": "2024-2025", "start_year": 2024, "end_year": 2025},
            format="json",
        )
        assert resp.status_code == 201

    def test_admin_can_activate_year(self, authenticated_client):
        year = AcademicYear.objects.create(name="2024-2025", start_year=2024, end_year=2025)
        resp = authenticated_client.post(
            f"/api/v1/academic-years/{year.id}/activate/"
        )
        assert resp.status_code == 200
