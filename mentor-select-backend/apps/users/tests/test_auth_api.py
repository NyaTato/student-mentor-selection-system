"""
认证模块 API 集成测试

覆盖端点：
- POST /api/v1/auth/login/        登录（有效/无效凭证、缺字段）
- POST /api/v1/auth/refresh/      刷新 Token
- POST /api/v1/auth/logout/       登出
- GET  /api/v1/auth/me/           当前用户信息
- POST /api/v1/auth/change-password/  修改密码

注：test_users.py 已覆盖管理员登录成功与管理员 me，此处补充其它端点与权限场景。
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.enums import UserRole, UserStatus
from apps.users.models import User


@pytest.mark.django_db
class TestLoginAPI:
    """登录端点 API 测试"""

    def test_login_success_returns_tokens(self, api_client, student_user):
        """有效凭证登录返回 access/refresh/user"""
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "student001", "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        data = resp.data["data"]
        assert "access" in data
        assert "refresh" in data
        assert data["user"]["username"] == "student001"
        assert data["user"]["role"] == UserRole.STUDENT.value

    def test_login_wrong_password(self, api_client, student_user):
        """错误密码登录失败（401）"""
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "student001", "password": "WrongPass!"},
            format="json",
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, api_client):
        """不存在的用户登录失败（401）"""
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "ghost", "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 401

    def test_login_disabled_user(self, api_client):
        """被禁用的用户不能登录"""
        user = User.objects.create_user(
            username="disabled001",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
        )
        user.status = UserStatus.DISABLED.value
        user.save(update_fields=["status"])
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "disabled001", "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 401

    def test_login_missing_password(self, api_client):
        """缺少密码字段返回 400"""
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "someone"},
            format="json",
        )
        assert resp.status_code == 400

    def test_login_missing_username(self, api_client):
        """缺少用户名字段返回 400"""
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 400

    def test_login_no_credentials(self, api_client):
        """空请求体返回 400"""
        resp = api_client.post("/api/v1/auth/login/", {}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestRefreshTokenAPI:
    """刷新 Token 端点 API 测试"""

    def test_refresh_token_success(self, api_client, student_user):
        """有效 refresh token 换取新 access"""
        refresh = RefreshToken.for_user(student_user)
        resp = api_client.post(
            "/api/v1/auth/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        assert resp.status_code == 200
        data = resp.data["data"]
        assert "access" in data
        assert "refresh" in data

    def test_refresh_token_invalid(self, api_client):
        """无效 refresh token 返回 401"""
        resp = api_client.post(
            "/api/v1/auth/refresh/",
            {"refresh": "invalid-token-string"},
            format="json",
        )
        assert resp.status_code == 401

    def test_refresh_token_missing(self, api_client):
        """缺少 refresh 字段返回 400（请求格式错误，不是 401）"""
        resp = api_client.post("/api/v1/auth/refresh/", {}, format="json")
        assert resp.status_code == 400

    def test_refresh_token_blank_rejected(self, api_client):
        """refresh 为空字符串同样属于格式错误 → 400"""
        resp = api_client.post(
            "/api/v1/auth/refresh/", {"refresh": ""}, format="json"
        )
        assert resp.status_code == 400

    def test_refresh_token_disabled_user_rejected(self, api_client, student_user):
        """账号被禁用后，旧 refresh token 不能再换取 access（401）"""
        refresh = RefreshToken.for_user(student_user)
        student_user.status = UserStatus.DISABLED.value
        student_user.save(update_fields=["status"])

        resp = api_client.post(
            "/api/v1/auth/refresh/", {"refresh": str(refresh)}, format="json"
        )
        assert resp.status_code == 401

    def test_refresh_token_deleted_user_rejected(self, api_client, student_user):
        """账号被软删除后，旧 refresh token 不能再换取 access（401）"""
        from django.utils import timezone

        refresh = RefreshToken.for_user(student_user)
        student_user.deleted_at = timezone.now()
        student_user.save(update_fields=["deleted_at"])

        resp = api_client.post(
            "/api/v1/auth/refresh/", {"refresh": str(refresh)}, format="json"
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestRefreshTokenRotation:
    """refresh 轮换 + 黑名单（ROTATE_REFRESH_TOKENS / BLACKLIST_AFTER_ROTATION）

    最终评审要求：AuthService 自定义路径必须真正走 SimpleJWT
    TokenRefreshSerializer，不能只把配置写在 settings 里而不生效。
    """

    REFRESH_URL = "/api/v1/auth/refresh/"

    def test_refresh_returns_new_token_and_blacklists_old(self, api_client, student_user):
        """刷新返回**不同**的 refresh，且旧 refresh 被拉黑后不可再用（401）"""
        from rest_framework_simplejwt.exceptions import TokenError

        old_refresh = RefreshToken.for_user(student_user)
        old_str = str(old_refresh)

        resp = api_client.post(self.REFRESH_URL, {"refresh": old_str}, format="json")
        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["access"]
        assert data["refresh"] != old_str, "开启了轮换，refresh 必须变化"

        # 旧 refresh 已进入黑名单（SimpleJWT 侧直接拒绝）
        with pytest.raises(TokenError):
            RefreshToken(old_str)

        # 旧 refresh 再次刷新 → 401
        again = api_client.post(self.REFRESH_URL, {"refresh": old_str}, format="json")
        assert again.status_code == 401

    def test_new_refresh_token_works_after_rotation(self, api_client, student_user):
        """轮换后的新 refresh 可继续刷新（且再次轮换）"""
        first = RefreshToken.for_user(student_user)
        resp1 = api_client.post(self.REFRESH_URL, {"refresh": str(first)}, format="json")
        assert resp1.status_code == 200
        new_refresh = resp1.data["data"]["refresh"]

        resp2 = api_client.post(self.REFRESH_URL, {"refresh": new_refresh}, format="json")
        assert resp2.status_code == 200
        assert resp2.data["data"]["access"]
        assert resp2.data["data"]["refresh"] != new_refresh

    def test_new_access_token_authenticates(self, api_client, student_user):
        """刷新出的新 access 可用于认证受保护接口"""
        refresh = RefreshToken.for_user(student_user)
        resp = api_client.post(self.REFRESH_URL, {"refresh": str(refresh)}, format="json")
        new_access = resp.data["data"]["access"]

        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        assert me.get("/api/v1/auth/me/").status_code == 200

    def test_disabled_account_rejected_and_refresh_not_rotated(
        self, api_client, student_user
    ):
        """账号禁用后刷新被拒（401），且不会签出新 token"""
        refresh = RefreshToken.for_user(student_user)
        student_user.status = UserStatus.DISABLED.value
        student_user.save(update_fields=["status"])

        resp = api_client.post(self.REFRESH_URL, {"refresh": str(refresh)}, format="json")
        assert resp.status_code == 401

    def test_deleted_account_rejected(self, api_client, student_user):
        """账号软删除后刷新被拒（401）"""
        from django.utils import timezone

        refresh = RefreshToken.for_user(student_user)
        student_user.deleted_at = timezone.now()
        student_user.save(update_fields=["deleted_at"])

        resp = api_client.post(self.REFRESH_URL, {"refresh": str(refresh)}, format="json")
        assert resp.status_code == 401

    def test_inactive_flag_rejected(self, api_client, student_user):
        """is_active=False（Django 层禁用）同样拒绝刷新"""
        refresh = RefreshToken.for_user(student_user)
        student_user.is_active = False
        student_user.save(update_fields=["is_active"])

        resp = api_client.post(self.REFRESH_URL, {"refresh": str(refresh)}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestLogoutAPI:
    """登出端点 API 测试"""

    def test_logout_success(self, authenticated_client, admin_user):
        """有效 refresh token 登出成功"""
        refresh = RefreshToken.for_user(admin_user)
        resp = authenticated_client.post(
            "/api/v1/auth/logout/",
            {"refresh": str(refresh)},
            format="json",
        )
        assert resp.status_code == 200

    def test_logout_invalid_token(self, authenticated_client):
        """无效 refresh token 登出返回 400"""
        resp = authenticated_client.post(
            "/api/v1/auth/logout/",
            {"refresh": "invalid-token-string"},
            format="json",
        )
        assert resp.status_code == 400

    def test_logout_missing_token(self, authenticated_client):
        """缺少 refresh 字段返回 400"""
        resp = authenticated_client.post(
            "/api/v1/auth/logout/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_logout_unauthenticated(self, api_client):
        """未认证用户不能登出（401）"""
        resp = api_client.post(
            "/api/v1/auth/logout/",
            {"refresh": "anything"},
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestMeAPI:
    """当前用户信息端点 API 测试"""

    def test_admin_me(self, authenticated_client, admin_user):
        """管理员获取自身信息"""
        resp = authenticated_client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["username"] == "admin001"
        assert data["role"] == UserRole.ADMIN.value
        assert data["admin_profile"] is None  # 未创建管理员档案

    def test_teacher_me(self, teacher_client, teacher_profile):
        """导师获取自身信息（含导师档案）"""
        resp = teacher_client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["username"] == "teacher001"
        assert data["role"] == UserRole.TEACHER.value
        assert data["teacher_profile"] is not None
        assert data["teacher_profile"]["name"] == "测试导师"

    def test_student_me(self, student_client, student_profile):
        """学生获取自身信息（含学生档案）"""
        resp = student_client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        data = resp.data["data"]
        assert data["username"] == "student001"
        assert data["role"] == UserRole.STUDENT.value
        assert data["student_profile"] is not None
        assert data["student_profile"]["name"] == "测试学生"

    def test_me_unauthenticated(self, api_client):
        """未认证用户不能访问 me（401）"""
        resp = api_client.get("/api/v1/auth/me/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestChangePasswordAPI:
    """修改密码端点 API 测试"""

    def test_change_password_success(self, authenticated_client, admin_user):
        """正确旧密码修改成功"""
        resp = authenticated_client.post(
            "/api/v1/auth/change-password/",
            {"old_password": "TestPass123!", "new_password": "BrandNew123!"},
            format="json",
        )
        assert resp.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.check_password("BrandNew123!")

    def test_change_password_wrong_old(self, authenticated_client, admin_user):
        """旧密码错误返回 400"""
        resp = authenticated_client.post(
            "/api/v1/auth/change-password/",
            {"old_password": "WrongOld!", "new_password": "BrandNew123!"},
            format="json",
        )
        assert resp.status_code == 400
        admin_user.refresh_from_db()
        assert admin_user.check_password("TestPass123!")

    def test_change_password_same_as_old(self, authenticated_client, admin_user):
        """新密码与旧密码相同返回 400"""
        resp = authenticated_client.post(
            "/api/v1/auth/change-password/",
            {"old_password": "TestPass123!", "new_password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 400

    def test_change_password_missing_fields(self, authenticated_client):
        """缺少字段返回 400"""
        resp = authenticated_client.post(
            "/api/v1/auth/change-password/",
            {"old_password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 400

    def test_change_password_unauthenticated(self, api_client):
        """未认证用户不能修改密码（401）"""
        resp = api_client.post(
            "/api/v1/auth/change-password/",
            {"old_password": "x", "new_password": "y"},
            format="json",
        )
        assert resp.status_code == 401

    def test_student_can_change_own_password(self, student_client, student_user):
        """学生可以修改自己的密码"""
        resp = student_client.post(
            "/api/v1/auth/change-password/",
            {"old_password": "TestPass123!", "new_password": "StudentNew123!"},
            format="json",
        )
        assert resp.status_code == 200
        student_user.refresh_from_db()
        assert student_user.check_password("StudentNew123!")
