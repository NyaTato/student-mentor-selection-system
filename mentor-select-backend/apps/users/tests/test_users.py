"""
用户模块测试
覆盖 Model / Serializer / Service / Permission
"""
import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.enums import UserRole, UserStatus
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import (
    AuthenticationFailedError,
    BusinessException,
    NotFoundError,
)
from apps.users.models import AdminProfile, User
from apps.users.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    UserSerializer,
)
from apps.users.services import AdminProfileService, AuthService, UserService


@pytest.mark.django_db
class TestUserModel:
    """User Model 测试"""

    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
        )
        assert user.id is not None
        assert user.username == "testuser"
        assert user.role == UserRole.STUDENT.value
        assert user.status == UserStatus.ACTIVE.value
        assert user.check_password("TestPass123!")

    def test_user_str(self):
        user = User.objects.create_user(
            username="testuser",
            password="TestPass123!",
        )
        assert str(user) == "testuser"

    def test_user_default_role(self):
        user = User.objects.create_user(
            username="defaultuser",
            password="TestPass123!",
        )
        assert user.role == UserRole.STUDENT.value

    def test_user_soft_delete(self):
        """软删除后默认 manager 不返回"""
        from django.utils import timezone

        user = User.objects.create_user(
            username="softdel",
            password="TestPass123!",
        )
        user.deleted_at = timezone.now()
        user.save(update_fields=["deleted_at"])

        # 默认 manager 不返回已删除用户
        assert not User.objects.filter(id=user.id).exists()
        # all_objects 返回所有
        assert User.all_objects.filter(id=user.id).exists()

    def test_admin_profile_creation(self):
        user = User.objects.create_user(
            username="admin001",
            password="TestPass123!",
            role=UserRole.ADMIN.value,
        )
        profile = AdminProfile.objects.create(user=user, name="管理员")
        assert profile.user_id == user.id
        assert profile.name == "管理员"
        assert str(profile) == "管理员"


@pytest.mark.django_db
class TestUserSerializer:
    """User Serializer 测试"""

    def test_login_serializer_valid(self):
        serializer = LoginSerializer(
            data={"username": "testuser", "password": "TestPass123!"}
        )
        assert serializer.is_valid()

    def test_login_serializer_missing_password(self):
        serializer = LoginSerializer(data={"username": "testuser"})
        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_login_serializer_missing_username(self):
        serializer = LoginSerializer(data={"password": "TestPass123!"})
        assert not serializer.is_valid()
        assert "username" in serializer.errors

    def test_change_password_serializer_valid(self):
        serializer = ChangePasswordSerializer(
            data={
                "old_password": "OldPass123!",
                "new_password": "NewPass123!",
            }
        )
        assert serializer.is_valid()

    def test_change_password_serializer_missing_fields(self):
        serializer = ChangePasswordSerializer(data={"old_password": "OldPass123!"})
        assert not serializer.is_valid()

    def test_user_serializer_read_fields(self):
        user = User.objects.create_user(
            username="testuser",
            password="TestPass123!",
            role=UserRole.TEACHER.value,
        )
        serializer = UserSerializer(user)
        data = serializer.data
        assert "id" in data
        assert "username" in data
        assert "role" in data
        assert "status" in data
        assert "password" not in data


@pytest.mark.django_db
class TestAuthService:
    """AuthService 测试"""

    def test_login_success(self):
        User.objects.create_user(
            username="loginuser",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
        )
        result = AuthService.login("loginuser", "TestPass123!")
        assert "access" in result
        assert "refresh" in result
        assert result["user"]["username"] == "loginuser"
        assert result["user"]["role"] == UserRole.STUDENT.value

    def test_login_wrong_password(self):
        User.objects.create_user(
            username="loginuser",
            password="TestPass123!",
        )
        with pytest.raises(AuthenticationFailedError):
            AuthService.login("loginuser", "WrongPass!")

    def test_login_user_not_found(self):
        with pytest.raises(AuthenticationFailedError):
            AuthService.login("nonexistent", "TestPass123!")

    def test_login_disabled_user(self):
        user = User.objects.create_user(
            username="disabled",
            password="TestPass123!",
        )
        user.status = UserStatus.DISABLED.value
        user.save(update_fields=["status"])
        with pytest.raises(AuthenticationFailedError):
            AuthService.login("disabled", "TestPass123!")

    def test_login_empty_credentials(self):
        from apps.common.exceptions import ValidationError

        with pytest.raises(ValidationError):
            AuthService.login("", "TestPass123!")
        with pytest.raises(ValidationError):
            AuthService.login("testuser", "")

    def test_logout_success(self):
        user = User.objects.create_user(
            username="logoutuser",
            password="TestPass123!",
        )
        refresh = RefreshToken.for_user(user)
        AuthService.logout(str(refresh))  # 不抛异常即通过

    def test_logout_invalid_token(self):
        from apps.common.exceptions import ValidationError

        with pytest.raises(ValidationError):
            AuthService.logout("invalid-token")

    def test_refresh_token_success(self):
        user = User.objects.create_user(
            username="refreshuser",
            password="TestPass123!",
        )
        refresh = RefreshToken.for_user(user)
        result = AuthService.refresh_token(str(refresh))
        assert "access" in result
        assert "refresh" in result

    def test_refresh_token_invalid(self):
        with pytest.raises(AuthenticationFailedError):
            AuthService.refresh_token("invalid-token")


@pytest.mark.django_db
class TestUserService:
    """UserService 测试"""

    def test_create_user_success(self):
        service = UserService()
        user = service.create({
            "username": "newuser",
            "password": "NewPass123!",
            "role": UserRole.TEACHER.value,
        })
        assert user.id is not None
        assert user.username == "newuser"
        assert user.check_password("NewPass123!")

    def test_create_user_duplicate_username(self):
        User.objects.create_user(
            username="dupuser",
            password="TestPass123!",
        )
        service = UserService()
        with pytest.raises(BusinessException) as exc_info:
            service.create({
                "username": "dupuser",
                "password": "TestPass123!",
            })
        assert exc_info.value.default_code == ErrorCode.USER_EXISTS

    def test_get_by_id(self):
        user = User.objects.create_user(
            username="getuser",
            password="TestPass123!",
        )
        service = UserService()
        result = service.get_by_id(user.id)
        assert result.id == user.id

    def test_get_by_id_not_found(self):
        service = UserService()
        with pytest.raises(NotFoundError):
            service.get_by_id(99999)

    def test_update_user(self):
        user = User.objects.create_user(
            username="updateuser",
            password="TestPass123!",
        )
        service = UserService()
        updated = service.update(user.id, {"status": UserStatus.DISABLED.value})
        assert updated.status == UserStatus.DISABLED.value

    def test_change_password_success(self):
        user = User.objects.create_user(
            username="pwduser",
            password="OldPass123!",
        )
        service = UserService()
        service.change_password(user.id, "OldPass123!", "NewPass123!")
        user.refresh_from_db()
        assert user.check_password("NewPass123!")

    def test_change_password_wrong_old(self):
        user = User.objects.create_user(
            username="pwduser",
            password="OldPass123!",
        )
        service = UserService()
        with pytest.raises(BusinessException) as exc_info:
            service.change_password(user.id, "WrongOld!", "NewPass123!")
        assert exc_info.value.default_code == ErrorCode.PASSWORD_INCORRECT

    def test_disable_user(self):
        user = User.objects.create_user(
            username="disableuser",
            password="TestPass123!",
        )
        service = UserService()
        service.disable(user.id)
        user.refresh_from_db()
        assert user.status == UserStatus.DISABLED.value

    def test_enable_user(self):
        user = User.objects.create_user(
            username="enableuser",
            password="TestPass123!",
        )
        user.status = UserStatus.DISABLED.value
        user.save()
        service = UserService()
        service.enable(user.id)
        user.refresh_from_db()
        assert user.status == UserStatus.ACTIVE.value

    def test_soft_delete_user(self):
        user = User.objects.create_user(
            username="deluser",
            password="TestPass123!",
        )
        service = UserService()
        service.delete(user.id)
        # 软删除后默认 manager 不返回
        assert not User.objects.filter(id=user.id).exists()


@pytest.mark.django_db
class TestAdminProfileService:
    """AdminProfileService 测试"""

    def test_create_admin_profile(self):
        user = User.objects.create_user(
            username="adminprofile",
            password="TestPass123!",
            role=UserRole.ADMIN.value,
        )
        service = AdminProfileService()
        profile = service.create({"user_id": user.id, "name": "管理员"})
        assert profile.user_id == user.id
        assert profile.name == "管理员"

    def test_create_duplicate_admin_profile(self):
        user = User.objects.create_user(
            username="dupadmin",
            password="TestPass123!",
            role=UserRole.ADMIN.value,
        )
        AdminProfile.objects.create(user=user, name="管理员")
        service = AdminProfileService()
        with pytest.raises(BusinessException):
            service.create({"user_id": user.id, "name": "管理员2"})

    def test_get_by_user_id(self):
        user = User.objects.create_user(
            username="getadmin",
            password="TestPass123!",
            role=UserRole.ADMIN.value,
        )
        AdminProfile.objects.create(user=user, name="管理员")
        service = AdminProfileService()
        profile = service.get_by_user_id(user.id)
        assert profile.name == "管理员"

    def test_get_by_user_id_not_found(self):
        service = AdminProfileService()
        with pytest.raises(NotFoundError):
            service.get_by_user_id(99999)


@pytest.mark.django_db
class TestUserPermission:
    """用户权限测试"""

    def test_admin_can_access_user_list(self, authenticated_client):
        """管理员可以访问用户列表"""
        resp = authenticated_client.get("/api/v1/users/")
        assert resp.status_code == 200

    def test_unauthenticated_cannot_access_user_list(self, api_client):
        """未认证用户不能访问用户列表"""
        resp = api_client.get("/api/v1/users/")
        assert resp.status_code == 401

    def test_student_cannot_access_user_list(self, student_client):
        """学生不能访问用户列表"""
        resp = student_client.get("/api/v1/users/")
        assert resp.status_code == 403

    def test_login_endpoint(self, api_client):
        """登录端点测试"""
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username="apitest",
            password="TestPass123!",
        )
        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "apitest", "password": "TestPass123!"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data["data"]
        assert "refresh" in resp.data["data"]

    def test_me_endpoint(self, authenticated_client):
        """获取当前用户信息"""
        resp = authenticated_client.get("/api/v1/auth/me/")
        assert resp.status_code == 200
        assert "username" in resp.data["data"]
