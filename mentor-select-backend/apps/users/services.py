"""
用户管理业务服务

包含：
- AuthService: 登录、登出、刷新 Token
- UserService: 用户 CRUD
- AdminProfileService: 管理员档案 CRUD
"""
import secrets
import time

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.enums import UserStatus
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import (
    AuthenticationFailedError,
    BusinessException,
    NotFoundError,
    ValidationError,
)
from apps.common.logger import get_logger, log_login
from apps.common.services import BaseService
from apps.monitoring.services import MetricsService
from apps.users.models import AdminProfile, User
from apps.users.repositories import AdminProfileRepository, UserRepository

logger = get_logger("users.services")


class AuthService:
    """认证服务：登录 / 登出 / 刷新 Token"""

    user_repository = UserRepository()

    @classmethod
    def login(cls, username: str, password: str) -> dict:
        """用户登录

        返回 {access, refresh, user:{id, username, role, status}}
        """
        start = time.perf_counter()
        success = False
        try:
            if not username or not password:
                raise ValidationError("用户名和密码不能为空")

            # 直接查库 + check_password，绕过 AUTHENTICATION_BACKENDS 以使用 SoftDeleteUserManager
            user = cls.user_repository.get_by_username(username)
            if user is None:
                log_login(user_id=None, username=username, success=False)
                raise AuthenticationFailedError("用户名或密码错误")

            if not user.check_password(password):
                log_login(user_id=user.id, username=username, success=False)
                raise AuthenticationFailedError("用户名或密码错误")

            if user.status != UserStatus.ACTIVE.value:
                log_login(user_id=user.id, username=username, success=False)
                raise AuthenticationFailedError(
                    "账号已被禁用，请联系管理员",
                )

            # 生成 JWT
            refresh = RefreshToken.for_user(user)
            refresh["role"] = user.role
            refresh["username"] = user.username

            log_login(user_id=user.id, username=username, success=True)
            logger.info("User login success: id=%s, role=%s", user.id, user.role)

            success = True
            return {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "role_display": user.get_role_display(),
                    "status": user.status,
                    "status_display": user.get_status_display(),
                },
            }
        finally:
            MetricsService.record_login(success, time.perf_counter() - start)

    @classmethod
    def logout(cls, refresh_token: str) -> None:
        """用户登出，将 refresh token 加入黑名单"""
        if not refresh_token:
            raise ValidationError("缺少 refresh token")

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            raise ValidationError(
                "refresh token 无效或已过期",
            ) from exc

        # 记录 JWT 失效（黑名单命中）
        MetricsService.record_jwt_expiry()
        logger.info("User logout success")

    @classmethod
    def refresh_token(cls, refresh_token: str) -> dict:
        """刷新 Token（SimpleJWT 规范路径：轮换 + 黑名单）

        返回 {access, refresh}

        实现要点（review-checkpoints.md 最终评审要求）：
        1. 先做**账号可用性前置校验**（存在 / 未删除 / 启用 / is_active），
           账号被禁用或删除后，旧 refresh token 立即不可用；
        2. 再交给 SimpleJWT 的 ``TokenRefreshSerializer`` 处理，
           从而使 ``ROTATE_REFRESH_TOKENS`` + ``BLACKLIST_AFTER_ROTATION``
           真正生效：旧 refresh 被加入黑名单，返回**新的** refresh token；
        3. 用户查询统一走 ``UserRepository``（Repository 层），Service 不直接写 ORM；
        4. 不记录任何 token 字符串。

        Raises:
            ValidationError: 缺少 refresh token（400，请求格式错误）
            AuthenticationFailedError: token 无效/过期/已黑名单，或账号不可用（401）
        """
        if not refresh_token:
            raise ValidationError("缺少 refresh token")

        user_id = cls._user_id_from_refresh(refresh_token)
        cls._assert_user_can_refresh(user_id)

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            # 记录 JWT 失效（过期/无效/已轮换进入黑名单）
            MetricsService.record_jwt_expiry()
            raise AuthenticationFailedError(
                "refresh token 无效或已过期",
            ) from exc

        data = serializer.validated_data
        MetricsService.record_jwt_refresh()
        return {
            "access": data["access"],
            # 开启轮换后必有新 refresh；未开启轮换时回退为原 token（保持响应契约）
            "refresh": data.get("refresh", refresh_token),
        }

    @classmethod
    def _user_id_from_refresh(cls, refresh_token: str) -> int:
        """从 refresh token 中解析用户 ID（不校验业务状态）"""
        from rest_framework_simplejwt.settings import api_settings

        try:
            token = RefreshToken(refresh_token)
        except TokenError as exc:
            MetricsService.record_jwt_expiry()
            raise AuthenticationFailedError(
                "refresh token 无效或已过期",
            ) from exc

        user_id = token.get(api_settings.USER_ID_CLAIM)
        if not user_id:
            raise AuthenticationFailedError("refresh token 缺少用户标识")
        return user_id

    @classmethod
    def _assert_user_can_refresh(cls, user_id: int) -> None:
        """校验 token 对应的账号当前仍可刷新（存在 / 未删除 / 启用 / is_active）

        查询经 ``UserRepository``（SoftDeleteUserManager 默认过滤软删除用户）。
        """
        user = cls.user_repository.get_by_id_or_none(user_id)
        if user is None or getattr(user, "deleted_at", None) is not None:
            raise AuthenticationFailedError("账号不存在或已被删除，无法刷新令牌")
        if (
            not user.is_active
            or getattr(user, "status", UserStatus.ACTIVE.value)
            != UserStatus.ACTIVE.value
        ):
            raise AuthenticationFailedError("账号已被禁用，无法刷新令牌")


class UserService(BaseService):
    """用户业务服务"""

    repository = UserRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询用户列表

        支持按 role / status 过滤
        """
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> User:
        return self.repository.get_with_profile(pk)

    def get_by_username(self, username: str) -> User | None:
        return self.repository.get_by_username(username)

    def create(self, validated_data: dict) -> User:
        """创建用户

        - 校验 username 唯一
        - 密码通过 set_password 哈希
        - R11-09: 密码可选，未填则系统生成随机密码（通过 _generated_password 返回给管理员）
        """
        username = validated_data.get("username")
        if self.repository.exists(username=username):
            raise BusinessException(
                f"用户名 {username} 已存在",
                code=ErrorCode.USER_EXISTS,
            )

        password = validated_data.pop("password", None)
        generated_password = None
        # R11-09: 密码可选，未填则系统生成随机密码（secrets.token_urlsafe 不可预测）
        if not password:
            password = self._generate_random_password()
            generated_password = password
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        # 瞬态属性：仅返回给管理员一次，不持久化
        if generated_password:
            user._generated_password = generated_password
        logger.info("User created: id=%s, username=%s", user.id, user.username)
        return user

    @staticmethod
    def _generate_random_password() -> str:
        """生成不可预测的随机密码（16 字符，满足 Django 密码强度要求）

        使用 secrets.token_urlsafe（密码学安全随机数生成器），
        替代可预测的 Mentor@{username} 默认密码。
        """
        return f"Mentor@{secrets.token_urlsafe(12)}"

    def update(self, pk: int, validated_data: dict) -> User:
        """更新用户

        - 若提供 password 则重新哈希
        - 若提供 username，校验唯一性（排除自身）
        - 若提供 status，同步 is_active（SimpleJWT 依据 is_active 校验 token）
        """
        user = self.repository.get_with_profile(pk)

        new_username = validated_data.get("username")
        if new_username and new_username != user.username:
            if self.repository.exists(username=new_username):
                raise BusinessException(
                    f"用户名 {new_username} 已存在",
                    code=ErrorCode.USER_EXISTS,
                )

        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(user, attr, value)

        # status 变更时同步 is_active，使禁用用户的现有 JWT 即时失效
        if "status" in validated_data:
            user.is_active = validated_data["status"] == UserStatus.ACTIVE.value

        if password:
            user.set_password(password)
        # 乐观锁版本 +1
        if hasattr(user, "version"):
            user.version = (user.version or 0) + 1
        user.save()
        logger.info("User updated: id=%s", user.id)
        return user

    def delete(self, pk: int) -> User:
        """软删除用户"""
        user = self.repository.get_with_profile(pk)
        from django.utils import timezone

        user.deleted_at = timezone.now()
        if hasattr(user, "version"):
            user.version = (user.version or 0) + 1
        user.save(update_fields=["deleted_at", "version", "updated_at"])
        logger.info("User soft deleted: id=%s", user.id)
        return user

    def change_password(self, pk: int, old_password: str, new_password: str) -> None:
        """修改密码"""
        user = self.repository.get_with_profile(pk)
        if not user.check_password(old_password):
            raise BusinessException(
                "原密码错误",
                code=ErrorCode.PASSWORD_INCORRECT,
            )
        user.set_password(new_password)
        if hasattr(user, "version"):
            user.version = (user.version or 0) + 1
        user.save(update_fields=["password", "version", "updated_at"])
        logger.info("User password changed: id=%s", user.id)

    def disable(self, pk: int) -> User:
        """禁用用户

        同步设置 is_active=False，使 SimpleJWT 立即拒绝该用户的现有 token。
        """
        user = self.repository.get_with_profile(pk)
        user.status = UserStatus.DISABLED.value
        user.is_active = False
        if hasattr(user, "version"):
            user.version = (user.version or 0) + 1
        user.save(update_fields=["status", "is_active", "version", "updated_at"])
        logger.info("User disabled: id=%s", user.id)
        return user

    def enable(self, pk: int) -> User:
        """启用用户

        同步设置 is_active=True，恢复 JWT 认证能力。
        """
        user = self.repository.get_with_profile(pk)
        user.status = UserStatus.ACTIVE.value
        user.is_active = True
        if hasattr(user, "version"):
            user.version = (user.version or 0) + 1
        user.save(update_fields=["status", "is_active", "version", "updated_at"])
        logger.info("User enabled: id=%s", user.id)
        return user


class AdminProfileService(BaseService):
    """管理员档案业务服务"""

    repository = AdminProfileRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        return self.repository.list(filters=filters, order_by=order_by or ["-user_id"])

    def get_by_id(self, pk: int) -> AdminProfile:
        return self.repository.get_by_id(pk)

    def get_by_user_id(self, user_id: int) -> AdminProfile:
        profile = self.repository.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError(f"AdminProfile (user_id={user_id}) 不存在")
        return profile

    def create(self, validated_data: dict) -> AdminProfile:
        """创建管理员档案"""
        user_id = validated_data.get("user_id")
        if user_id and self.repository.exists(user_id=user_id):
            raise BusinessException(
                f"用户 {user_id} 的管理员档案已存在",
                code=ErrorCode.USER_PROFILE_NOT_FOUND,
            )
        return self.repository.create(**validated_data)

    def update(self, pk: int, validated_data: dict) -> AdminProfile:
        instance = self.repository.get_by_id(pk)
        return self.repository.update(instance, validated_data)
