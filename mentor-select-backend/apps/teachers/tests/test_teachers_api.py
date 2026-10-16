"""
导师模块 API 集成测试

覆盖端点：
TeacherProfileViewSet（/api/v1/teachers/profiles/）：
  - list / retrieve / create / update / delete / me / 过滤
TeacherQuotaViewSet（/api/v1/teachers/quotas/）：
  - list / retrieve / create / update / by-year / batch

注：test_teachers.py 已覆盖 model/service 与基本权限（list、me），
此处补充 API 层 CRUD 与名额端点。
"""
import pytest

from apps.common.enums import UserRole, UserStatus
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.users.models import User


def _make_teacher_user(username="newteacher", teacher_number="0002"):
    """创建一个无档案的导师用户"""
    return User.objects.create_user(
        username=username,
        password="TestPass123!",
        role=UserRole.TEACHER.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.mark.django_db
class TestTeacherProfileListRetrieveAPI:
    """导师档案 list / retrieve API 测试"""

    def test_admin_list_profiles(
        self, authenticated_client, teacher_profile
    ):
        """管理员查询导师档案列表"""
        resp = authenticated_client.get("/api/v1/teachers/profiles/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) >= 1

    def test_student_can_list_profiles(self, student_client, teacher_profile):
        """学生可以查看导师列表（IsAdminOrReadOnly：只读允许）"""
        resp = student_client.get("/api/v1/teachers/profiles/")
        assert resp.status_code == 200

    def test_retrieve_profile(self, authenticated_client, teacher_profile):
        """查询单个导师档案（PK=user_id）"""
        resp = authenticated_client.get(
            f"/api/v1/teachers/profiles/{teacher_profile.user_id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"]["teacher_number"] == teacher_profile.teacher_number

    def test_retrieve_not_found(self, authenticated_client):
        """查询不存在的导师档案返回 404"""
        resp = authenticated_client.get("/api/v1/teachers/profiles/99999/")
        assert resp.status_code == 404

    def test_list_filter_by_college(
        self, authenticated_client, teacher_profile
    ):
        """按学院过滤"""
        resp = authenticated_client.get(
            "/api/v1/teachers/profiles/?college=计算机"
        )
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_list_filter_by_keyword(
        self, authenticated_client, teacher_profile
    ):
        """按关键字（工号/姓名）过滤"""
        resp = authenticated_client.get(
            f"/api/v1/teachers/profiles/?keyword={teacher_profile.teacher_number}"
        )
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_list_unauthenticated(self, api_client):
        """未认证用户不能查看导师列表"""
        resp = api_client.get("/api/v1/teachers/profiles/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestTeacherProfileCreateAPI:
    """导师档案 create API 测试"""

    def test_admin_create_profile_success(self, authenticated_client):
        """管理员创建导师档案成功"""
        user = _make_teacher_user()
        resp = authenticated_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": "0002",
                "name": "新导师",
                "college": "计算机学院",
                "research_area": "机器学习",
            },
            format="json",
        )
        assert resp.status_code == 201
        data = resp.data["data"]
        assert data["teacher_number"] == "0002"
        assert data["name"] == "新导师"

    def test_student_cannot_create_profile(self, student_client):
        """学生不能创建导师档案（IsAdminOrReadOnly -> 403）"""
        user = _make_teacher_user()
        resp = student_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": "0003",
                "name": "新导师",
                "college": "计算机学院",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_cannot_create_profile(self, teacher_client):
        """导师不能创建导师档案（IsAdminOrReadOnly -> 403）"""
        user = _make_teacher_user()
        resp = teacher_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": "0004",
                "name": "新导师",
                "college": "计算机学院",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_create_duplicate_teacher_number(
        self, authenticated_client, teacher_profile
    ):
        """重复工号创建失败"""
        user = _make_teacher_user()
        resp = authenticated_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": teacher_profile.teacher_number,
                "name": "新导师",
                "college": "计算机学院",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_create_invalid_teacher_number(
        self, authenticated_client
    ):
        """非法工号格式（含字母）返回 400"""
        user = _make_teacher_user()
        resp = authenticated_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": "ABCD",  # 非 4-10 位数字
                "name": "新导师",
                "college": "计算机学院",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_create_invalid_name(self, authenticated_client):
        """非法姓名（单字符）返回 400"""
        user = _make_teacher_user()
        resp = authenticated_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": "0005",
                "name": "A",  # 少于 2 字符
                "college": "计算机学院",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_create_missing_required_field(self, authenticated_client):
        """缺少必填字段返回 400"""
        user = _make_teacher_user()
        resp = authenticated_client.post(
            "/api/v1/teachers/profiles/",
            {
                "user": user.id,
                "teacher_number": "0006",
                "name": "新导师",
                # 缺少 college
            },
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTeacherProfileUpdateAPI:
    """导师档案 update API 测试"""

    def test_admin_update_profile(self, authenticated_client, teacher_profile):
        """管理员更新导师档案"""
        resp = authenticated_client.patch(
            f"/api/v1/teachers/profiles/{teacher_profile.user_id}/",
            {"college": "软件学院", "title": "教授"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["college"] == "软件学院"
        assert resp.data["data"]["title"] == "教授"

    def test_student_cannot_update(self, student_client, teacher_profile):
        """学生不能更新导师档案（403）"""
        resp = student_client.patch(
            f"/api/v1/teachers/profiles/{teacher_profile.user_id}/",
            {"college": "软件学院"},
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_update_own_profile(self, teacher_client, teacher_profile):
        """导师不能通过通用 update 端点修改（IsAdminOrReadOnly -> 403）

        注：导师自助更新需通过 me 端点（本系统 me 仅查询）。
        """
        resp = teacher_client.patch(
            f"/api/v1/teachers/profiles/{teacher_profile.user_id}/",
            {"college": "软件学院"},
            format="json",
        )
        assert resp.status_code == 403

    def test_update_not_found(self, authenticated_client):
        """更新不存在的导师档案返回 404"""
        resp = authenticated_client.patch(
            "/api/v1/teachers/profiles/99999/",
            {"college": "软件学院"},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestTeacherProfileDeleteAPI:
    """导师档案 delete API 测试"""

    def test_admin_delete_profile(self, authenticated_client, teacher_user):
        """管理员软删除导师档案"""
        TeacherProfile.objects.create(
            user=teacher_user,
            teacher_number="0007",
            name="待删除",
            college="计算机学院",
        ) if False else None
        # 直接复用已有 teacher_profile
        # 为避免影响其它测试，单独创建一个
        user = _make_teacher_user("deltmp", "0008")
        TeacherProfile.objects.create(
            user=user, teacher_number="0008", name="待删", college="CS"
        )
        resp = authenticated_client.delete(f"/api/v1/teachers/profiles/{user.id}/")
        assert resp.status_code == 200
        # 软删除后默认 manager 不返回
        assert not TeacherProfile.objects.filter(user_id=user.id).exists()

    def test_student_cannot_delete(self, student_client, teacher_profile):
        """学生不能删除导师档案（403）"""
        resp = student_client.delete(
            f"/api/v1/teachers/profiles/{teacher_profile.user_id}/"
        )
        assert resp.status_code == 403

    def test_delete_not_found(self, authenticated_client):
        """删除不存在的导师档案返回 404"""
        resp = authenticated_client.delete(
            "/api/v1/teachers/profiles/99999/"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestTeacherProfileMeAPI:
    """导师 me 端点 API 测试"""

    def test_teacher_me_success(self, teacher_client, teacher_profile):
        """导师查看自己的档案"""
        resp = teacher_client.get("/api/v1/teachers/profiles/me/")
        assert resp.status_code == 200
        assert resp.data["data"]["teacher_number"] == teacher_profile.teacher_number

    def test_student_cannot_access_me(self, student_client):
        """学生不能访问导师 me 端点（403）"""
        resp = student_client.get("/api/v1/teachers/profiles/me/")
        assert resp.status_code == 403

    def test_admin_cannot_access_teacher_me(self, authenticated_client):
        """管理员非导师角色，访问 me 端点被 IsTeacher 拦截（403）"""
        resp = authenticated_client.get("/api/v1/teachers/profiles/me/")
        assert resp.status_code == 403

    def test_me_unauthenticated(self, api_client):
        """未认证访问 me 返回 401"""
        resp = api_client.get("/api/v1/teachers/profiles/me/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestTeacherQuotaListRetrieveAPI:
    """导师名额 list / retrieve API 测试"""

    def test_admin_list_quotas(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """管理员查询名额列表"""
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=5,
        )
        resp = authenticated_client.get("/api/v1/teachers/quotas/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_student_can_read_quotas_but_cannot_write(
        self, student_client, teacher_profile, academic_year
    ):
        """名额读契约（Task 02 有意变更）：已认证用户可读汇总名额。

        学生选导师必须能看到剩余名额，因此 list/retrieve/by_year 对已认证开放；
        写操作（create/update/destroy/batch）仍为管理员专属（403）。
        """
        TeacherQuota.objects.create(
            academic_year=academic_year, teacher=teacher_profile, max_quota=5
        )
        resp = student_client.get("/api/v1/teachers/quotas/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1
        for field in ("id", "academic_year", "teacher", "max_quota"):
            assert field in items[0]

        resp = student_client.post(
            "/api/v1/teachers/quotas/",
            {"academic_year": academic_year.id, "teacher": teacher_profile.user_id, "max_quota": 9},
            format="json",
        )
        assert resp.status_code == 403

    def test_teacher_can_read_quotas_but_cannot_write(
        self, teacher_client, teacher_profile, academic_year
    ):
        """导师同样只能读名额，不能写（写操作 IsAdmin）。"""
        TeacherQuota.objects.create(
            academic_year=academic_year, teacher=teacher_profile, max_quota=5
        )
        resp = teacher_client.get("/api/v1/teachers/quotas/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

        resp = teacher_client.post(
            "/api/v1/teachers/quotas/",
            {"academic_year": academic_year.id, "teacher": teacher_profile.user_id, "max_quota": 9},
            format="json",
        )
        assert resp.status_code == 403

    def test_retrieve_quota(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """查询单个名额"""
        quota = TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=5,
        )
        resp = authenticated_client.get(f"/api/v1/teachers/quotas/{quota.id}/")
        assert resp.status_code == 200
        assert resp.data["data"]["max_quota"] == 5

    def test_retrieve_quota_not_found(self, authenticated_client):
        """查询不存在的名额返回 404"""
        resp = authenticated_client.get("/api/v1/teachers/quotas/99999/")
        assert resp.status_code == 404

    def test_list_filter_by_academic_year(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """按学年过滤"""
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=5,
        )
        resp = authenticated_client.get(
            f"/api/v1/teachers/quotas/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_list_unauthenticated(self, api_client):
        """未认证访问名额列表返回 401"""
        resp = api_client.get("/api/v1/teachers/quotas/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestTeacherQuotaCreateAPI:
    """导师名额 create API 测试"""

    def test_admin_create_quota_success(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """管理员创建名额成功"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "max_quota": 8,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["data"]["max_quota"] == 8

    def test_student_cannot_create_quota(self, student_client, academic_year, teacher_profile):
        """学生不能创建名额（403）"""
        resp = student_client.post(
            "/api/v1/teachers/quotas/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "max_quota": 8,
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_create_duplicate_quota(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """重复创建（同年同导师）失败"""
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=3,
        )
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "max_quota": 5,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_create_invalid_quota_value(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """名额超限（>99）返回 400"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "max_quota": 200,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_create_negative_quota(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """负数名额返回 400"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "max_quota": -1,
            },
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTeacherQuotaUpdateAPI:
    """导师名额 update API 测试"""

    def test_admin_update_quota(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """管理员更新名额"""
        quota = TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=3,
        )
        resp = authenticated_client.patch(
            f"/api/v1/teachers/quotas/{quota.id}/",
            {"max_quota": 10},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"]["max_quota"] == 10

    def test_student_cannot_update_quota(
        self, student_client, teacher_profile, academic_year
    ):
        """学生不能更新名额（403）"""
        quota = TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=3,
        )
        resp = student_client.patch(
            f"/api/v1/teachers/quotas/{quota.id}/",
            {"max_quota": 10},
            format="json",
        )
        assert resp.status_code == 403

    def test_update_quota_not_found(self, authenticated_client):
        """更新不存在的名额返回 404"""
        resp = authenticated_client.patch(
            "/api/v1/teachers/quotas/99999/",
            {"max_quota": 10},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestTeacherQuotaByYearAPI:
    """按学年查询名额 API 测试"""

    def test_by_year_success(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """按学年查询所有名额"""
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=5,
        )
        resp = authenticated_client.get(
            f"/api/v1/teachers/quotas/by-year/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1

    def test_by_year_empty(self, authenticated_client, academic_year):
        """无名额时返回空列表"""
        resp = authenticated_client.get(
            f"/api/v1/teachers/quotas/by-year/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["data"] == []

    def test_by_year_student_can_read(
        self, student_client, teacher_profile, academic_year
    ):
        """读契约：学生可按学年查询汇总名额（选导师必需），不再 403。"""
        TeacherQuota.objects.create(
            academic_year=academic_year, teacher=teacher_profile, max_quota=5
        )
        resp = student_client.get(
            f"/api/v1/teachers/quotas/by-year/{academic_year.id}/"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1
        assert resp.data["data"][0]["max_quota"] == 5


@pytest.mark.django_db
class TestTeacherQuotaBatchAPI:
    """批量设置名额 API 测试"""

    def test_batch_set_success(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """管理员批量设置名额"""
        # 第二个导师
        user2 = _make_teacher_user("teacher002", "0009")
        teacher2 = TeacherProfile.objects.create(
            user=user2, teacher_number="0009", name="李教授", college="CS"
        )
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/batch/",
            {
                "academic_year": academic_year.id,
                "quotas": [
                    {"teacher_id": teacher_profile.user_id, "max_quota": 5},
                    {"teacher_id": teacher2.user_id, "max_quota": 3},
                ],
            },
            format="json",
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 2

    def test_batch_set_update_existing(
        self, authenticated_client, teacher_profile, academic_year
    ):
        """批量设置已存在的名额会更新"""
        TeacherQuota.objects.create(
            academic_year=academic_year,
            teacher=teacher_profile,
            max_quota=1,
        )
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/batch/",
            {
                "academic_year": academic_year.id,
                "quotas": [
                    {"teacher_id": teacher_profile.user_id, "max_quota": 10},
                ],
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["data"][0]["max_quota"] == 10

    def test_batch_set_student_forbidden(self, student_client, academic_year):
        """学生不能批量设置名额（403）"""
        resp = student_client.post(
            "/api/v1/teachers/quotas/batch/",
            {
                "academic_year": academic_year.id,
                "quotas": [{"teacher_id": 1, "max_quota": 5}],
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_batch_set_empty_quotas(
        self, authenticated_client, academic_year
    ):
        """空 quotas 列表返回 400（min_length=1）"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/batch/",
            {"academic_year": academic_year.id, "quotas": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_batch_set_missing_field(self, authenticated_client):
        """缺少字段返回 400"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/batch/",
            {"quotas": [{"teacher_id": 1, "max_quota": 5}]},
            format="json",
        )
        assert resp.status_code == 400

    def test_batch_set_invalid_quota(
        self, authenticated_client, academic_year, teacher_profile
    ):
        """quotas 中 max_quota 超限返回 400"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/batch/",
            {
                "academic_year": academic_year.id,
                "quotas": [
                    {"teacher_id": teacher_profile.user_id, "max_quota": 200},
                ],
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_batch_set_missing_teacher_id(
        self, authenticated_client, academic_year
    ):
        """quotas 缺少 teacher_id 返回 400"""
        resp = authenticated_client.post(
            "/api/v1/teachers/quotas/batch/",
            {
                "academic_year": academic_year.id,
                "quotas": [{"max_quota": 5}],
            },
            format="json",
        )
        assert resp.status_code == 400
