"""
认证视图
登录、退出、获取当前用户信息
用户管理 ViewSet
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.response import ApiResponse
from apps.common.viewsets import BaseApiResponseViewSet
from apps.users.serializers import (
    AdminProfileSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    RefreshTokenRequestSerializer,
    UserProfileSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.services import AdminProfileService, AuthService, UserService

auth_service = AuthService()
user_service = UserService()
admin_profile_service = AdminProfileService()


class LoginView(APIView):
    """登录视图

    不需要认证，POST 用户名密码返回 JWT。
    """

    serializer_class = LoginSerializer
    permission_classes = []

    @extend_schema(
        tags=["认证"],
        summary="用户登录",
        request=LoginSerializer,
        responses={200: dict},
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = auth_service.login(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        return ApiResponse.success(data=data, message="登录成功")


class LogoutView(APIView):
    """退出视图

    需要认证，将 refresh token 加入黑名单。
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["认证"],
        summary="用户登出",
        request={"refresh": str},
        responses={200: dict},
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        auth_service.logout(refresh_token)
        return ApiResponse.success(message="退出成功")


class RefreshTokenView(APIView):
    """刷新 Token 视图

    不需要认证（但需要有效的 refresh token）。

    安全要求（全部由 ``AuthService.refresh_token`` 实现）：
    - 刷新前校验**当前用户仍然存在、未删除、已启用**（否则账号被禁用/删除后，
      旧 refresh token 仍可不断换取新 access token）；
    - 走 SimpleJWT ``TokenRefreshSerializer``，使
      ``ROTATE_REFRESH_TOKENS`` + ``BLACKLIST_AFTER_ROTATION`` 生效：
      旧 refresh 被拉黑，返回新的 refresh token。
    请求体经 RefreshTokenRequestSerializer 校验：
    缺少 / 空白 refresh 字段 → 400（格式错误），
    无效 / 过期 / 已轮换（黑名单）token 或不可用账号 → 401。
    """

    permission_classes = []

    @extend_schema(
        tags=["认证"],
        summary="刷新 Token",
        request=RefreshTokenRequestSerializer,
        responses={200: dict},
    )
    def post(self, request, *args, **kwargs):
        serializer = RefreshTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data["refresh"]
        data = auth_service.refresh_token(refresh_token)
        return ApiResponse.success(data=data, message="刷新成功")


class CurrentUserView(APIView):
    """当前用户信息视图

    需要认证，返回当前登录用户的完整信息。
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["认证"], summary="获取当前用户信息", responses={200: UserProfileSerializer})
    def get(self, request, *args, **kwargs):
        serializer = UserProfileSerializer(request.user)
        return ApiResponse.success(data=serializer.data, message="获取用户信息成功")


class ChangePasswordView(APIView):
    """修改密码视图

    需要认证，提交 old_password + new_password。
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["认证"],
        summary="修改密码",
        request=ChangePasswordSerializer,
        responses={200: dict},
    )
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_service.change_password(
            pk=request.user.id,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return ApiResponse.success(message="密码修改成功")


@extend_schema_view(
    list=extend_schema(tags=["用户管理"], summary="查询用户列表"),
    retrieve=extend_schema(tags=["用户管理"], summary="查询单个用户"),
    create=extend_schema(tags=["用户管理"], summary="创建用户"),
    update=extend_schema(tags=["用户管理"], summary="更新用户"),
    partial_update=extend_schema(tags=["用户管理"], summary="部分更新用户"),
    destroy=extend_schema(tags=["用户管理"], summary="删除用户"),
)
class UserViewSet(BaseApiResponseViewSet):
    """用户 ViewSet"""

    queryset = user_service.repository.get_queryset()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        """支持按 role / status / keyword 过滤"""
        queryset = self.queryset
        role = self.request.query_params.get("role")
        status = self.request.query_params.get("status")
        keyword = self.request.query_params.get("keyword")
        if role:
            queryset = queryset.filter(role=role)
        if status:
            queryset = queryset.filter(status=status)
        if keyword:
            queryset = queryset.filter(username__icontains=keyword)
        return queryset

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        # 使用 Service 创建
        instance = user_service.create(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        # 通过 Service 更新，Service 内部处理乐观锁版本号
        instance = user_service.update(
            serializer.instance.id, serializer.validated_data
        )
        serializer.instance = instance

    def perform_destroy(self, instance):
        user_service.delete(instance.id)


@extend_schema_view(
    list=extend_schema(tags=["用户管理"], summary="查询管理员档案列表"),
    retrieve=extend_schema(tags=["用户管理"], summary="查询单个管理员档案"),
    create=extend_schema(tags=["用户管理"], summary="创建管理员档案"),
    update=extend_schema(tags=["用户管理"], summary="更新管理员档案"),
    partial_update=extend_schema(tags=["用户管理"], summary="部分更新管理员档案"),
    destroy=extend_schema(tags=["用户管理"], summary="删除管理员档案"),
)
class AdminProfileViewSet(BaseApiResponseViewSet):
    """管理员档案 ViewSet"""

    queryset = admin_profile_service.repository.get_queryset()
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        queryset = self.queryset
        keyword = self.request.query_params.get("keyword")
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return queryset

    def perform_create(self, serializer):
        instance = admin_profile_service.create(serializer.validated_data)
        serializer.instance = instance
