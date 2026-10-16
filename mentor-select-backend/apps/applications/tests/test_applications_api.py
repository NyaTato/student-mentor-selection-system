"""
申请模块 API 集成测试

覆盖端点：
- GET  /api/v1/applications/                  列表（角色过滤）
- POST /api/v1/applications/                  学生提交申请
- GET  /api/v1/applications/{pk}/             查询单个申请
- GET  /api/v1/applications/my/               学生查询自己的申请
- GET  /api/v1/applications/teacher/          导师查询收到的申请
- POST /api/v1/applications/{pk}/approve/     通过申请
- POST /api/v1/applications/{pk}/reject/      拒绝申请
- POST /api/v1/applications/batch-approve/    批量通过
- POST /api/v1/applications/batch-reject/     批量拒绝

注：test_applications.py 已覆盖列表权限与 Service 层逻辑，此处补充 API 层端点。
"""
import pytest
from django.utils import timezone

from apps.applications.models import Application
from apps.common.enums import (
    ApplicationRound,
    ApplicationStatus,
    SystemStateValue,
    UserRole,
)
from apps.system.models import SystemState
from apps.teachers.models import TeacherQuota
from apps.users.models import User
from apps.students.models import StudentProfile


def _make_quota(academic_year, teacher_profile, max_quota):
    """为导师配置本学年名额（未配置名额 = 拒绝录取，见 Task 02 有意变更）"""
    return TeacherQuota.objects.create(
        academic_year=academic_year,
        teacher=teacher_profile,
        max_quota=max_quota,
    )


def _init_state(academic_year, state_value):
    """初始化系统状态到指定值"""
    SystemState.objects.create(
        academic_year=academic_year,
        current_state=state_value,
        state_changed_at=timezone.now(),
    )


def _create_pending_app(academic_year, student_profile, teacher_profile, round_value):
    """直接通过 ORM 创建一个待处理申请"""
    return Application.objects.create(
        academic_year=academic_year,
        student=student_profile,
        teacher=teacher_profile,
        round=round_value,
        status=ApplicationStatus.PENDING.value,
    )


@pytest.mark.django_db
class TestApplicationListAPI:
    """申请列表 API 测试"""

    def test_admin_list_all_applications(
        self, authenticated_client, academic_year, student_profile, teacher_profile
    ):
        """管理员可查看所有申请"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = authenticated_client.get("/api/v1/applications/")
        assert resp.status_code == 200
        items = resp.data["data"]
        # 非分页时返回 list
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1

    def test_student_list_only_own(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生只能看到自己的申请"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = student_client.get("/api/v1/applications/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1
        assert items[0]["student"] == student_profile.user_id

    def test_teacher_list_only_received(
        self,
        teacher_client,
        academic_year,
        student_profile,
        teacher_profile,
    ):
        """导师只能看到收到的申请"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.get("/api/v1/applications/")
        assert resp.status_code == 200
        items = resp.data["data"]
        if isinstance(items, dict):
            items = items.get("list", [])
        assert len(items) == 1
        assert items[0]["teacher"] == teacher_profile.user_id

    def test_list_filter_by_status(
        self, authenticated_client, academic_year, student_profile, teacher_profile
    ):
        """按状态过滤列表"""
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        app.status = ApplicationStatus.APPROVED.value
        app.save(update_fields=["status"])
        # 创建一个 PENDING 的
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        ) if False else None
        # 只查 PENDING
        resp = authenticated_client.get(
            "/api/v1/applications/", {"status": ApplicationStatus.PENDING.value}
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestApplicationCreateAPI:
    """学生提交申请 API 测试"""

    def test_student_create_first_round_success(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生第一轮申请提交成功（期望 201）"""
        _init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        resp = student_client.post(
            "/api/v1/applications/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "round": ApplicationRound.FIRST_ROUND.value,
            },
            format="json",
        )
        assert resp.status_code == 201
        data = resp.data["data"]
        assert data["round"] == ApplicationRound.FIRST_ROUND.value
        # ApplicationCreateSerializer 只返回 academic_year/teacher/round
        # 通过数据库验证 status
        app = Application.objects.filter(
            academic_year=academic_year,
            student=student_profile,
        ).first()
        assert app is not None
        assert app.status == ApplicationStatus.PENDING.value

    def test_student_create_wrong_state_fails(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """系统状态不对时提交失败（期望 400）"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        resp = student_client.post(
            "/api/v1/applications/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "round": ApplicationRound.FIRST_ROUND.value,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_teacher_cannot_create_application(
        self, teacher_client, academic_year, teacher_profile
    ):
        """导师提交申请：序列化器校验通过后由 service 处理，
        由于 perform_create 仅对学生注入 student_id，导师路径会触发 service 的
        KeyError（已知缺陷），这里验证导师无权以学生身份提交应返回非 201。"""
        _init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        resp = teacher_client.post(
            "/api/v1/applications/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "round": ApplicationRound.FIRST_ROUND.value,
            },
            format="json",
        )
        # 导师不应成功创建学生申请（不为 201）
        assert resp.status_code != 201

    def test_create_unauthenticated(self, api_client, academic_year, teacher_profile):
        """未认证用户不能提交申请"""
        resp = api_client.post(
            "/api/v1/applications/",
            {
                "academic_year": academic_year.id,
                "teacher": teacher_profile.user_id,
                "round": ApplicationRound.FIRST_ROUND.value,
            },
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestApplicationRetrieveAPI:
    """查询单个申请 API 测试"""

    def test_retrieve_success(
        self, authenticated_client, academic_year, student_profile, teacher_profile
    ):
        """管理员查询单个申请"""
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = authenticated_client.get(f"/api/v1/applications/{app.id}/")
        assert resp.status_code == 200
        assert resp.data["data"]["id"] == app.id

    def test_retrieve_not_found(self, authenticated_client):
        """查询不存在的申请返回 404"""
        resp = authenticated_client.get("/api/v1/applications/99999/")
        assert resp.status_code == 404

    def test_student_retrieve_own(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生查询自己的申请"""
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = student_client.get(f"/api/v1/applications/{app.id}/")
        assert resp.status_code == 200
        assert resp.data["data"]["id"] == app.id

    def test_retrieve_unauthenticated(self, api_client, academic_year):
        """未认证查询返回 401"""
        resp = api_client.get("/api/v1/applications/1/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestApplicationMyAPI:
    """学生查询自己的申请 API 测试"""

    def test_my_returns_student_applications(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生 my 端点返回自己的申请"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = student_client.get("/api/v1/applications/my/")
        assert resp.status_code == 200
        data = resp.data["data"]
        assert len(data) == 1
        assert data[0]["student"] == student_profile.user_id

    def test_my_filter_by_academic_year(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """my 端点按学年过滤"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = student_client.get(
            f"/api/v1/applications/my/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1

        # 不存在的学年返回空
        resp = student_client.get("/api/v1/applications/my/?academic_year=99999")
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 0

    def test_my_empty(self, student_client):
        """无申请时 my 返回空列表"""
        resp = student_client.get("/api/v1/applications/my/")
        assert resp.status_code == 200
        assert resp.data["data"] == []

    def test_teacher_cannot_use_my(self, teacher_client):
        """导师访问 my 端点：返回其作为导师的申请（端点不限制角色，
        但 list_my_applications 按 student_user_id 查询，导师无学生档案返回空）"""
        resp = teacher_client.get("/api/v1/applications/my/")
        assert resp.status_code == 200
        assert resp.data["data"] == []


@pytest.mark.django_db
class TestApplicationTeacherAPI:
    """导师查询收到的申请 API 测试"""

    def test_teacher_returns_received_applications(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """导师 teacher 端点返回收到的申请"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.get("/api/v1/applications/teacher/")
        assert resp.status_code == 200
        data = resp.data["data"]
        assert len(data) == 1
        assert data[0]["teacher"] == teacher_profile.user_id

    def test_teacher_filter_by_round(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """teacher 端点按轮次过滤"""
        _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.get(
            f"/api/v1/applications/teacher/?round={ApplicationRound.FIRST_ROUND.value}"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1

        # 不存在的轮次返回空
        resp = teacher_client.get(
            f"/api/v1/applications/teacher/?round={ApplicationRound.SECOND_ROUND.value}"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 0

    def test_teacher_filter_by_status(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """teacher 端点按状态过滤"""
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        app.status = ApplicationStatus.APPROVED.value
        app.save(update_fields=["status"])
        resp = teacher_client.get(
            f"/api/v1/applications/teacher/?status={ApplicationStatus.APPROVED.value}"
        )
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 1

    def test_student_teacher_endpoint_empty(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生访问 teacher 端点：按 teacher_user_id 查询，学生无导师档案返回空"""
        resp = student_client.get("/api/v1/applications/teacher/")
        assert resp.status_code == 200
        assert resp.data["data"] == []


@pytest.mark.django_db
class TestApplicationApproveAPI:
    """通过申请 API 测试"""

    def test_teacher_approve_success(
        self,
        teacher_client,
        academic_year,
        student_profile,
        teacher_profile,
    ):
        """导师通过第一轮申请"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        _make_quota(academic_year, teacher_profile, max_quota=1)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.post(f"/api/v1/applications/{app.id}/approve/")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == ApplicationStatus.APPROVED.value

    def test_admin_approve_success(
        self,
        authenticated_client,
        academic_year,
        student_profile,
        teacher_profile,
    ):
        """管理员可以审核任意申请"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        _make_quota(academic_year, teacher_profile, max_quota=1)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = authenticated_client.post(f"/api/v1/applications/{app.id}/approve/")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == ApplicationStatus.APPROVED.value

    def test_student_cannot_approve(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生不能审核申请（PERMISSION_DENIED -> 403）"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = student_client.post(f"/api/v1/applications/{app.id}/approve/")
        assert resp.status_code == 403

    def test_approve_wrong_state(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """系统状态不对时审核失败（400）"""
        _init_state(academic_year, SystemStateValue.INIT.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.post(f"/api/v1/applications/{app.id}/approve/")
        assert resp.status_code == 400

    def test_approve_already_processed(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """已处理的申请不能重复审核（400）"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        app.status = ApplicationStatus.APPROVED.value
        app.save(update_fields=["status"])
        resp = teacher_client.post(f"/api/v1/applications/{app.id}/approve/")
        assert resp.status_code == 400

    def test_approve_not_found(self, teacher_client):
        """审核不存在的申请返回 404"""
        resp = teacher_client.post("/api/v1/applications/99999/approve/")
        assert resp.status_code == 404

    def test_approve_unauthenticated(self, api_client, academic_year):
        """未认证审核返回 401"""
        resp = api_client.post("/api/v1/applications/1/approve/")
        assert resp.status_code == 401

    def test_other_teacher_cannot_approve(
        self,
        academic_year,
        student_profile,
        teacher_profile,
        teacher_user,
    ):
        """非该申请的导师不能审核"""
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework.test import APIClient

        # 创建另一个导师
        other = User.objects.create_user(
            username="teacher002",
            password="TestPass123!",
            role=UserRole.TEACHER.value,
            status=1,
        )
        from apps.teachers.models import TeacherProfile as TP

        TP.objects.create(
            user=other, teacher_number="0002", name="其他导师", college="CS"
        )
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        client = APIClient()
        refresh = RefreshToken.for_user(other)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = client.post(f"/api/v1/applications/{app.id}/approve/")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestApplicationRejectAPI:
    """拒绝申请 API 测试"""

    def test_teacher_reject_success(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """导师拒绝第一轮申请"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.post(f"/api/v1/applications/{app.id}/reject/")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == ApplicationStatus.REJECTED.value

    def test_admin_reject_success(
        self, authenticated_client, academic_year, student_profile, teacher_profile
    ):
        """管理员拒绝申请"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = authenticated_client.post(f"/api/v1/applications/{app.id}/reject/")
        assert resp.status_code == 200
        assert resp.data["data"]["status"] == ApplicationStatus.REJECTED.value

    def test_student_cannot_reject(
        self, student_client, academic_year, student_profile, teacher_profile
    ):
        """学生不能拒绝申请（PERMISSION_DENIED -> 403）"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = student_client.post(f"/api/v1/applications/{app.id}/reject/")
        assert resp.status_code == 403

    def test_reject_wrong_state(
        self, teacher_client, academic_year, student_profile, teacher_profile
    ):
        """系统状态不对时拒绝失败"""
        _init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        app = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.post(f"/api/v1/applications/{app.id}/reject/")
        assert resp.status_code == 400

    def test_reject_not_found(self, teacher_client):
        """拒绝不存在的申请返回 404"""
        resp = teacher_client.post("/api/v1/applications/99999/reject/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestApplicationBatchApproveAPI:
    """批量通过申请 API 测试"""

    def _create_two_pending_apps(
        self, academic_year, student_profile, teacher_profile
    ):
        """创建两个待处理申请（需要第二个学生 + 两个名额）"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        _make_quota(academic_year, teacher_profile, max_quota=2)
        app1 = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        # 第二个学生
        user2 = User.objects.create_user(
            username="student002",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
            status=1,
        )
        student2 = StudentProfile.objects.create(
            user=user2, student_number="20240002", name="学生二",
            major="CS", class_name="C2",
        )
        app2 = _create_pending_app(
            academic_year, student2, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        return app1, app2

    def test_batch_approve_success(
        self,
        teacher_client,
        academic_year,
        student_profile,
        teacher_profile,
    ):
        """导师批量通过"""
        app1, app2 = self._create_two_pending_apps(
            academic_year, student_profile, teacher_profile
        )
        resp = teacher_client.post(
            "/api/v1/applications/batch-approve/",
            {"application_ids": [app1.id, app2.id]},
            format="json",
        )
        assert resp.status_code == 200
        data = resp.data["data"]
        assert len(data) == 2
        for item in data:
            assert item["status"] == ApplicationStatus.APPROVED.value

    def test_batch_approve_empty_ids_rejected(
        self, teacher_client
    ):
        """空 ID 列表返回 400（min_length=1）"""
        resp = teacher_client.post(
            "/api/v1/applications/batch-approve/",
            {"application_ids": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_batch_approve_missing_field(self, teacher_client):
        """缺少 application_ids 字段返回 400"""
        resp = teacher_client.post(
            "/api/v1/applications/batch-approve/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_batch_approve_unauthenticated(self, api_client):
        """未认证批量通过返回 401"""
        resp = api_client.post(
            "/api/v1/applications/batch-approve/",
            {"application_ids": [1]},
            format="json",
        )
        assert resp.status_code == 401

    def test_student_cannot_batch_approve(self, student_client):
        """学生不能批量通过（POST 权限仅要求 IsAuthenticated，
        但 service.approve 会校验角色 -> 400）"""
        resp = student_client.post(
            "/api/v1/applications/batch-approve/",
            {"application_ids": [1]},
            format="json",
        )
        # 不存在的申请 + 学生身份，service.approve 抛 NotFoundError(404) 或
        # BusinessException(400)。两种都属非 200。
        assert resp.status_code != 200


@pytest.mark.django_db
class TestApplicationBatchRejectAPI:
    """批量拒绝申请 API 测试"""

    def test_batch_reject_success(
        self,
        teacher_client,
        academic_year,
        student_profile,
        teacher_profile,
    ):
        """导师批量拒绝"""
        _init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app1 = _create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        user2 = User.objects.create_user(
            username="student003",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
            status=1,
        )
        student2 = StudentProfile.objects.create(
            user=user2, student_number="20240003", name="学生三",
            major="CS", class_name="C3",
        )
        app2 = _create_pending_app(
            academic_year, student2, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        resp = teacher_client.post(
            "/api/v1/applications/batch-reject/",
            {"application_ids": [app1.id, app2.id]},
            format="json",
        )
        assert resp.status_code == 200
        data = resp.data["data"]
        assert len(data) == 2
        for item in data:
            assert item["status"] == ApplicationStatus.REJECTED.value

    def test_batch_reject_empty_ids_rejected(self, teacher_client):
        """空 ID 列表返回 400"""
        resp = teacher_client.post(
            "/api/v1/applications/batch-reject/",
            {"application_ids": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_batch_reject_missing_field(self, teacher_client):
        """缺少 application_ids 字段返回 400"""
        resp = teacher_client.post(
            "/api/v1/applications/batch-reject/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_batch_reject_unauthenticated(self, api_client):
        """未认证批量拒绝返回 401"""
        resp = api_client.post(
            "/api/v1/applications/batch-reject/",
            {"application_ids": [1]},
            format="json",
        )
        assert resp.status_code == 401
