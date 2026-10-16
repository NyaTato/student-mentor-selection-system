"""
公告模块测试
覆盖 Model / Repository / Service / Serializer / API / Permission
"""
import pytest
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.announcements.repositories import AnnouncementRepository
from apps.announcements.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    AnnouncementUpdateSerializer,
)
from apps.announcements.services import AnnouncementService
from apps.common.enums import UserRole
from apps.common.exceptions import BusinessException, NotFoundError
from apps.users.models import User

ANNOUNCEMENT_LIST_URL = "/api/v1/announcements/"


def _detail_url(pk):
    return f"{ANNOUNCEMENT_LIST_URL}{pk}/"


@pytest.fixture
def announcement(admin_user, academic_year):
    """公告实例（未发布）"""
    return Announcement.objects.create(
        academic_year=academic_year,
        title="测试公告",
        content="测试内容",
        is_published=False,
        created_by=admin_user,
    )


@pytest.fixture
def published_announcement(admin_user, academic_year):
    """已发布公告"""
    return Announcement.objects.create(
        academic_year=academic_year,
        title="已发布公告",
        content="已发布内容",
        is_published=True,
        published_at=timezone.now(),
        created_by=admin_user,
    )


@pytest.mark.django_db
class TestAnnouncementModel:
    """Announcement Model 测试"""

    def test_create_announcement(self, admin_user, academic_year):
        ann = Announcement.objects.create(
            academic_year=academic_year,
            title="公告1",
            content="内容1",
            created_by=admin_user,
        )
        assert ann.id is not None
        assert ann.title == "公告1"
        assert ann.content == "内容1"
        assert ann.academic_year_id == academic_year.id
        assert ann.created_by_id == admin_user.id

    def test_announcement_str(self, announcement):
        assert str(announcement) == "测试公告"

    def test_default_is_published(self, admin_user, academic_year):
        ann = Announcement.objects.create(
            academic_year=academic_year,
            title="默认公告",
            content="内容",
            created_by=admin_user,
        )
        assert ann.is_published is False

    def test_default_published_at_is_none(self, admin_user, academic_year):
        ann = Announcement.objects.create(
            academic_year=academic_year,
            title="默认公告",
            content="内容",
            created_by=admin_user,
        )
        assert ann.published_at is None

    def test_default_version(self, admin_user, academic_year):
        ann = Announcement.objects.create(
            academic_year=academic_year,
            title="版本公告",
            content="内容",
            created_by=admin_user,
        )
        assert ann.version == 1

    def test_ordering(self, admin_user, academic_year):
        first = Announcement.objects.create(
            academic_year=academic_year,
            title="第一",
            content="内容",
            created_by=admin_user,
        )
        second = Announcement.objects.create(
            academic_year=academic_year,
            title="第二",
            content="内容",
            created_by=admin_user,
        )
        qs = list(Announcement.objects.all())
        # ordering = ["-id"], 较新的在前
        assert qs[0].id == second.id
        assert qs[1].id == first.id

    def test_soft_delete(self, announcement):
        """软删除后默认 manager 不返回，all_objects 返回全部"""
        from django.utils import timezone

        ann_id = announcement.id
        announcement.deleted_at = timezone.now()
        announcement.save(update_fields=["deleted_at"])

        assert not Announcement.objects.filter(id=ann_id).exists()
        assert Announcement.all_objects.filter(id=ann_id).exists()


@pytest.mark.django_db
class TestAnnouncementRepository:
    """AnnouncementRepository 测试"""

    def test_list(self, announcement, published_announcement):
        repo = AnnouncementRepository()
        qs = repo.list()
        assert qs.count() == 2

    def test_list_with_filters(self, announcement, published_announcement):
        repo = AnnouncementRepository()
        qs = repo.list(filters={"is_published": True})
        assert qs.count() == 1
        assert qs.first().id == published_announcement.id

    def test_list_with_order_by(self, announcement, published_announcement):
        repo = AnnouncementRepository()
        qs = repo.list(order_by=["id"])
        assert list(qs)[0].id == announcement.id

    def test_get_by_id(self, announcement):
        repo = AnnouncementRepository()
        result = repo.get_by_id(announcement.id)
        assert result.id == announcement.id
        assert result.title == "测试公告"

    def test_get_by_id_not_found(self):
        repo = AnnouncementRepository()
        with pytest.raises(NotFoundError):
            repo.get_by_id(99999)

    def test_get_queryset_select_related(self, announcement):
        """get_queryset 应 select_related academic_year / created_by"""
        repo = AnnouncementRepository()
        qs = repo.get_queryset()
        # 查询不抛异常即说明关联存在
        obj = qs.get(id=announcement.id)
        assert obj.academic_year.name is not None
        assert obj.created_by.username is not None

    def test_list_by_academic_year(self, admin_user, academic_year):
        # 创建另一个学年
        from apps.academic_year.models import AcademicYear
        from apps.common.enums import AcademicYearStatus

        other_year = AcademicYear.objects.create(
            name="2023-2024",
            start_year=2023,
            end_year=2024,
            status=AcademicYearStatus.INACTIVE.value,
        )
        Announcement.objects.create(
            academic_year=academic_year,
            title="本学年公告",
            content="内容",
            created_by=admin_user,
        )
        Announcement.objects.create(
            academic_year=other_year,
            title="其他学年公告",
            content="内容",
            created_by=admin_user,
        )

        repo = AnnouncementRepository()
        qs = repo.list_by_academic_year(academic_year.id)
        assert qs.count() == 1
        assert qs.first().title == "本学年公告"

    def test_list_by_academic_year_only_published(
        self, announcement, published_announcement, academic_year
    ):
        repo = AnnouncementRepository()
        # 包含未发布（announcement + published_announcement）
        all_qs = repo.list_by_academic_year(academic_year.id, only_published=False)
        assert all_qs.count() == 2

        # 仅已发布
        published_qs = repo.list_by_academic_year(
            academic_year.id, only_published=True
        )
        assert published_qs.count() == 1
        assert published_qs.first().id == published_announcement.id

    def test_create(self, admin_user, academic_year):
        repo = AnnouncementRepository()
        ann = repo.create(
            academic_year=academic_year,
            title="仓库创建",
            content="内容",
            is_published=False,
            created_by=admin_user,
        )
        assert ann.id is not None
        assert ann.title == "仓库创建"

    def test_update(self, announcement):
        repo = AnnouncementRepository()
        updated = repo.update(announcement, {"title": "更新标题"})
        assert updated.title == "更新标题"
        # update 会自增 version
        assert updated.version == announcement.version + 1 or updated.version >= 2

    def test_soft_delete(self, announcement):
        repo = AnnouncementRepository()
        repo.soft_delete(announcement)
        assert not Announcement.objects.filter(id=announcement.id).exists()
        assert Announcement.all_objects.filter(id=announcement.id).exists()


@pytest.mark.django_db
class TestAnnouncementService:
    """AnnouncementService 测试"""

    def test_create(self, admin_user, academic_year):
        service = AnnouncementService()
        ann = service.create({
            "academic_year": academic_year,
            "title": "服务创建",
            "content": "内容",
            "is_published": False,
            "created_by": admin_user,
        })
        assert ann.id is not None
        assert ann.title == "服务创建"
        assert ann.created_by_id == admin_user.id

    def test_create_with_is_published_auto_fills_published_at(
        self, admin_user, academic_year
    ):
        """is_published=True 时自动填充 published_at"""
        service = AnnouncementService()
        ann = service.create({
            "academic_year": academic_year,
            "title": "直接发布",
            "content": "内容",
            "is_published": True,
            "created_by": admin_user,
        })
        assert ann.is_published is True
        assert ann.published_at is not None

    def test_create_not_published_no_published_at(self, admin_user, academic_year):
        """is_published=False 时 published_at 为 None"""
        service = AnnouncementService()
        ann = service.create({
            "academic_year": academic_year,
            "title": "未发布",
            "content": "内容",
            "is_published": False,
            "created_by": admin_user,
        })
        assert ann.published_at is None

    def test_get_by_id(self, announcement):
        service = AnnouncementService()
        result = service.get_by_id(announcement.id)
        assert result.id == announcement.id

    def test_get_by_id_not_found(self):
        service = AnnouncementService()
        with pytest.raises(NotFoundError):
            service.get_by_id(99999)

    def test_list(self, announcement, published_announcement):
        service = AnnouncementService()
        qs = service.list()
        assert qs.count() == 2

    def test_list_with_filters(self, announcement, published_announcement):
        service = AnnouncementService()
        qs = service.list(filters={"is_published": True})
        assert qs.count() == 1
        assert qs.first().id == published_announcement.id

    def test_list_default_order_by_id_desc(
        self, admin_user, academic_year
    ):
        service = AnnouncementService()
        a1 = service.create({
            "academic_year": academic_year,
            "title": "a1",
            "content": "c",
            "is_published": False,
            "created_by": admin_user,
        })
        a2 = service.create({
            "academic_year": academic_year,
            "title": "a2",
            "content": "c",
            "is_published": False,
            "created_by": admin_user,
        })
        qs = list(service.list())
        assert qs[0].id == a2.id
        assert qs[1].id == a1.id

    def test_list_by_academic_year(self, announcement, published_announcement, academic_year):
        service = AnnouncementService()
        qs = service.list_by_academic_year(academic_year.id)
        assert qs.count() == 2

    def test_list_by_academic_year_only_published(
        self, announcement, published_announcement, academic_year
    ):
        service = AnnouncementService()
        qs = service.list_by_academic_year(academic_year.id, only_published=True)
        assert qs.count() == 1
        assert qs.first().id == published_announcement.id

    def test_update(self, announcement):
        service = AnnouncementService()
        updated = service.update(announcement.id, {"title": "服务更新标题"})
        assert updated.title == "服务更新标题"

    def test_update_not_found(self):
        service = AnnouncementService()
        with pytest.raises(NotFoundError):
            service.update(99999, {"title": "x"})

    def test_delete(self, announcement):
        service = AnnouncementService()
        result = service.delete(announcement.id)
        assert result.id == announcement.id
        assert not Announcement.objects.filter(id=announcement.id).exists()
        assert Announcement.all_objects.filter(id=announcement.id).exists()

    def test_delete_not_found(self):
        service = AnnouncementService()
        with pytest.raises(NotFoundError):
            service.delete(99999)

    def test_publish(self, announcement):
        service = AnnouncementService()
        result = service.publish(announcement.id)
        assert result.is_published is True
        assert result.published_at is not None

    def test_publish_already_published_raises(self, published_announcement):
        service = AnnouncementService()
        with pytest.raises(BusinessException):
            service.publish(published_announcement.id)

    def test_unpublish(self, published_announcement):
        service = AnnouncementService()
        result = service.unpublish(published_announcement.id)
        assert result.is_published is False
        # published_at 保留作为历史记录
        assert result.published_at is not None

    def test_unpublish_not_published_raises(self, announcement):
        service = AnnouncementService()
        with pytest.raises(BusinessException):
            service.unpublish(announcement.id)


@pytest.mark.django_db
class TestAnnouncementSerializer:
    """Announcement Serializer 测试"""

    def test_serializer_read_fields(self, announcement):
        serializer = AnnouncementSerializer(announcement)
        data = serializer.data
        assert "id" in data
        assert "academic_year" in data
        assert "title" in data
        assert "content" in data
        assert "is_published" in data
        assert "published_at" in data
        assert "created_by" in data
        assert "version" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "deleted_at" in data

    def test_create_serializer_valid(self, academic_year):
        data = {
            "academic_year": academic_year.id,
            "title": "序列化创建",
            "content": "内容",
            "is_published": False,
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_create_serializer_missing_academic_year(self):
        """academic_year 为必填"""
        data = {
            "title": "无学年",
            "content": "内容",
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "academic_year" in serializer.errors

    def test_create_serializer_missing_title(self, academic_year):
        data = {
            "academic_year": academic_year.id,
            "content": "内容",
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_create_serializer_missing_content(self, academic_year):
        data = {
            "academic_year": academic_year.id,
            "title": "标题",
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_validate_title_empty(self, academic_year):
        data = {
            "academic_year": academic_year.id,
            "title": "   ",
            "content": "内容",
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_validate_title_too_long(self, academic_year):
        data = {
            "academic_year": academic_year.id,
            "title": "a" * 101,
            "content": "内容",
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_validate_content_empty(self, academic_year):
        data = {
            "academic_year": academic_year.id,
            "title": "标题",
            "content": "   ",
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_create_serializer_created_by_readonly(self, academic_year):
        """created_by 字段为只读，不应出现在 validated_data"""
        data = {
            "academic_year": academic_year.id,
            "title": "标题",
            "content": "内容",
            "is_published": False,
        }
        serializer = AnnouncementCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert "created_by" not in serializer.validated_data

    def test_update_serializer_academic_year_readonly(
        self, announcement, academic_year
    ):
        """更新时 academic_year 为只读"""
        from apps.academic_year.models import AcademicYear
        from apps.common.enums import AcademicYearStatus

        other_year = AcademicYear.objects.create(
            name="2023-2024",
            start_year=2023,
            end_year=2024,
            status=AcademicYearStatus.INACTIVE.value,
        )
        data = {
            "academic_year": other_year.id,
            "title": "更新标题",
            "content": "更新内容",
        }
        serializer = AnnouncementUpdateSerializer(announcement, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors
        # academic_year 不应出现在 validated_data（只读）
        assert "academic_year" not in serializer.validated_data
        assert serializer.validated_data["title"] == "更新标题"

    def test_update_serializer_created_by_readonly(self, announcement, admin_user):
        """更新时 created_by 为只读"""
        data = {"created_by": admin_user.id, "title": "更新标题"}
        serializer = AnnouncementUpdateSerializer(announcement, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors
        assert "created_by" not in serializer.validated_data

    def test_is_published_default_in_serializer(self, announcement):
        """序列化输出 is_published 字段"""
        serializer = AnnouncementSerializer(announcement)
        assert serializer.data["is_published"] is False


@pytest.mark.django_db
class TestAnnouncementAPI:
    """公告 API / View 测试"""

    def test_admin_list_announcements(
        self, authenticated_client, announcement, published_announcement
    ):
        resp = authenticated_client.get(ANNOUNCEMENT_LIST_URL)
        assert resp.status_code == 200
        # 分页格式: data.list
        data = resp.data["data"]
        assert "list" in data
        assert data["total"] == 2

    def test_admin_list_filter_by_academic_year(
        self, authenticated_client, announcement, academic_year, admin_user
    ):
        from apps.academic_year.models import AcademicYear
        from apps.common.enums import AcademicYearStatus

        other_year = AcademicYear.objects.create(
            name="2023-2024",
            start_year=2023,
            end_year=2024,
            status=AcademicYearStatus.INACTIVE.value,
        )
        from apps.announcements.models import Announcement

        Announcement.objects.create(
            academic_year=other_year,
            title="其他学年",
            content="内容",
            created_by=admin_user,
        )

        resp = authenticated_client.get(
            ANNOUNCEMENT_LIST_URL, {"academic_year": academic_year.id}
        )
        assert resp.status_code == 200
        items = resp.data["data"]["list"]
        assert len(items) == 1
        assert items[0]["title"] == "测试公告"

    def test_admin_list_filter_by_is_published(
        self, authenticated_client, announcement, published_announcement
    ):
        resp = authenticated_client.get(
            ANNOUNCEMENT_LIST_URL, {"is_published": "true"}
        )
        assert resp.status_code == 200
        items = resp.data["data"]["list"]
        assert len(items) == 1
        assert items[0]["is_published"] is True

    def test_admin_list_filter_by_not_published(
        self, authenticated_client, announcement, published_announcement
    ):
        resp = authenticated_client.get(
            ANNOUNCEMENT_LIST_URL, {"is_published": "false"}
        )
        assert resp.status_code == 200
        items = resp.data["data"]["list"]
        assert len(items) == 1
        assert items[0]["is_published"] is False

    def test_admin_create_announcement(self, authenticated_client, academic_year):
        payload = {
            "academic_year": academic_year.id,
            "title": "API创建公告",
            "content": "API内容",
            "is_published": False,
        }
        resp = authenticated_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["data"]["title"] == "API创建公告"
        assert resp.data["data"]["is_published"] is False
        # created_by 自动填充为当前用户
        from apps.announcements.models import Announcement

        ann = Announcement.objects.get(title="API创建公告")
        assert ann.created_by.username == "admin001"

    def test_admin_create_published_announcement_auto_published_at(
        self, authenticated_client, academic_year
    ):
        payload = {
            "academic_year": academic_year.id,
            "title": "直接发布公告",
            "content": "内容",
            "is_published": True,
        }
        resp = authenticated_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 201
        assert resp.data["data"]["is_published"] is True
        assert resp.data["data"]["published_at"] is not None

    def test_admin_create_announcement_missing_academic_year(
        self, authenticated_client
    ):
        payload = {"title": "无学年", "content": "内容"}
        resp = authenticated_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 400

    def test_admin_create_announcement_empty_title(
        self, authenticated_client, academic_year
    ):
        payload = {
            "academic_year": academic_year.id,
            "title": "   ",
            "content": "内容",
        }
        resp = authenticated_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 400

    def test_admin_retrieve_announcement(self, authenticated_client, announcement):
        resp = authenticated_client.get(_detail_url(announcement.id))
        assert resp.status_code == 200
        assert resp.data["data"]["id"] == announcement.id
        assert resp.data["data"]["title"] == "测试公告"

    def test_admin_retrieve_not_found(self, authenticated_client):
        resp = authenticated_client.get(_detail_url(99999))
        assert resp.status_code == 404

    def test_admin_update_announcement(self, authenticated_client, announcement):
        payload = {"title": "更新后的标题", "content": "更新后的内容"}
        resp = authenticated_client.put(
            _detail_url(announcement.id), payload, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["title"] == "更新后的标题"

    def test_admin_partial_update_announcement(
        self, authenticated_client, announcement
    ):
        resp = authenticated_client.patch(
            _detail_url(announcement.id), {"title": "部分更新"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["title"] == "部分更新"

    def test_admin_delete_announcement(self, authenticated_client, announcement):
        resp = authenticated_client.delete(_detail_url(announcement.id))
        assert resp.status_code == 200
        # 软删除后默认 manager 不返回
        assert not Announcement.objects.filter(id=announcement.id).exists()

    def test_admin_publish_announcement(
        self, authenticated_client, announcement
    ):
        resp = authenticated_client.post(
            _detail_url(announcement.id) + "publish/"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["is_published"] is True
        assert resp.data["data"]["published_at"] is not None

    def test_admin_publish_already_published_raises(
        self, authenticated_client, published_announcement
    ):
        resp = authenticated_client.post(
            _detail_url(published_announcement.id) + "publish/"
        )
        assert resp.status_code == 400

    def test_admin_unpublish_announcement(
        self, authenticated_client, published_announcement
    ):
        resp = authenticated_client.post(
            _detail_url(published_announcement.id) + "unpublish/"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["is_published"] is False

    def test_admin_unpublish_not_published_raises(
        self, authenticated_client, announcement
    ):
        resp = authenticated_client.post(
            _detail_url(announcement.id) + "unpublish/"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAnnouncementPermission:
    """公告权限测试

    读契约（Task 02 有意变更）：list/retrieve 对**已认证用户**开放，
    但非管理员**只能**看到 `is_published=True` 的公告（草稿不可见，
    即使显式请求 `?is_published=false`）。
    写操作（create/update/destroy/publish/unpublish）仍为管理员专属。
    """

    def test_unauthenticated_cannot_list(self, api_client):
        resp = api_client.get(ANNOUNCEMENT_LIST_URL)
        assert resp.status_code == 401

    def test_unauthenticated_cannot_create(self, api_client, academic_year):
        payload = {
            "academic_year": academic_year.id,
            "title": "x",
            "content": "y",
        }
        resp = api_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 401

    def test_student_list_only_published(
        self, student_client, announcement, published_announcement
    ):
        """学生可读列表，但草稿不泄漏。"""
        resp = student_client.get(ANNOUNCEMENT_LIST_URL)
        assert resp.status_code == 200
        data = resp.data["data"]
        items = data["list"] if isinstance(data, dict) else data
        titles = [item["title"] for item in items]
        assert "已发布公告" in titles
        assert "测试公告" not in titles

    def test_student_cannot_create(self, student_client, academic_year):
        payload = {
            "academic_year": academic_year.id,
            "title": "x",
            "content": "y",
        }
        resp = student_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 403

    def test_student_retrieve_published_but_not_draft(
        self, student_client, announcement, published_announcement
    ):
        """已发布公告详情可读；草稿详情 404（不是 403，也不泄漏存在性之外的字段）。"""
        resp = student_client.get(_detail_url(published_announcement.id))
        assert resp.status_code == 200
        assert resp.data["data"]["title"] == "已发布公告"

        resp = student_client.get(_detail_url(announcement.id))
        assert resp.status_code == 404

    def test_student_cannot_update(self, student_client, announcement):
        resp = student_client.patch(
            _detail_url(announcement.id), {"title": "hack"}, format="json"
        )
        assert resp.status_code == 403

    def test_student_cannot_delete(self, student_client, announcement):
        resp = student_client.delete(_detail_url(announcement.id))
        assert resp.status_code == 403

    def test_student_cannot_publish(self, student_client, announcement):
        resp = student_client.post(_detail_url(announcement.id) + "publish/")
        assert resp.status_code == 403

    def test_teacher_list_only_published(
        self, teacher_client, announcement, published_announcement
    ):
        """导师同样可读列表，但只能看到已发布公告。"""
        resp = teacher_client.get(ANNOUNCEMENT_LIST_URL)
        assert resp.status_code == 200
        data = resp.data["data"]
        items = data["list"] if isinstance(data, dict) else data
        titles = [item["title"] for item in items]
        assert "已发布公告" in titles
        assert "测试公告" not in titles

    def test_teacher_cannot_create(self, teacher_client, academic_year):
        payload = {
            "academic_year": academic_year.id,
            "title": "x",
            "content": "y",
        }
        resp = teacher_client.post(ANNOUNCEMENT_LIST_URL, payload, format="json")
        assert resp.status_code == 403

    def test_teacher_retrieve_published_but_not_draft(
        self, teacher_client, announcement, published_announcement
    ):
        resp = teacher_client.get(_detail_url(published_announcement.id))
        assert resp.status_code == 200

        resp = teacher_client.get(_detail_url(announcement.id))
        assert resp.status_code == 404

    def test_teacher_cannot_update(self, teacher_client, announcement):
        resp = teacher_client.patch(
            _detail_url(announcement.id), {"title": "hack"}, format="json"
        )
        assert resp.status_code == 403

    def test_teacher_cannot_delete(self, teacher_client, announcement):
        resp = teacher_client.delete(_detail_url(announcement.id))
        assert resp.status_code == 403

    def test_teacher_cannot_publish(self, teacher_client, announcement):
        resp = teacher_client.post(_detail_url(announcement.id) + "publish/")
        assert resp.status_code == 403

    def test_admin_can_list(self, authenticated_client):
        resp = authenticated_client.get(ANNOUNCEMENT_LIST_URL)
        assert resp.status_code == 200

    def test_admin_can_create(self, authenticated_client, academic_year):
        payload = {
            "academic_year": academic_year.id,
            "title": "管理员创建",
            "content": "内容",
        }
        resp = authenticated_client.post(
            ANNOUNCEMENT_LIST_URL, payload, format="json"
        )
        assert resp.status_code == 201
