"""user_view - 用户接口

权限策略（本模块收紧项已标注）：
- login: AllowAny（公开接口）
- get_user: IsAuthenticated
- list_users: IsAdmin（收紧：用户列表含全部账号信息，不允许普通用户枚举）
- change_password: IsAuthenticated + 本人（收紧：只能修改自己的密码，改他人返回 403）
- 写操作（create/update/delete/reset_password/disable/enable）: IsAdmin
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from api.schema import (
    ChangePasswordSerializer,
    IdSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
    UserListQuerySerializer,
    UserUpdateSerializer,
)
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.response import ApiResponse
from constant.error_code import ErrorCode
from lib.service.user_service import UserService


def _user_to_dict(user) -> dict:
    """User 对象转 dict（不含密码）"""
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    """用户登录

    POST /api/v2/users/login
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    user = UserService.login(
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )
    if user is None:
        return ApiResponse.error(code=ErrorCode.LOGIN_FAILED, message="用户名或密码错误", http_status_code=401)
    return ApiResponse.success(data=_user_to_dict(user), message="登录成功")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user(request: Request, user_id: int) -> Response:
    """获取用户信息

    GET /api/v2/users/{user_id}
    """
    user = UserService.get_user(user_id)
    if user is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="用户不存在", http_status_code=404)
    return ApiResponse.success(data=_user_to_dict(user), message="查询成功")


@api_view(["GET"])
@permission_classes([IsAdmin])
def list_users(request: Request) -> Response:
    """查询用户列表（分页）

    GET /api/v2/users/list?page=1&page_size=20

    权限：仅管理员（收紧，用户列表不得对普通用户开放）
    """
    serializer = UserListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    result = UserService.list_users(
        page=serializer.validated_data["page"],
        page_size=serializer.validated_data["page_size"],
    )
    result["list"] = [_user_to_dict(u) for u in result["list"]]
    return ApiResponse.success(data=result, message="查询成功")


@api_view(["POST"])
@permission_classes([IsAdmin])
def create_user(request: Request) -> Response:
    """创建用户

    POST /api/v2/users/create
    """
    serializer = UserCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        user_id = UserService.create_user(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            role=serializer.validated_data["role"],
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data={"user_id": user_id}, message="创建成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def update_user(request: Request, user_id: int) -> Response:
    """更新用户信息

    PUT /api/v2/users/{user_id}/update
    """
    serializer = UserUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        affected = UserService.update_user(user_id, **serializer.validated_data)
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data={"affected": affected}, message="更新成功")


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_password(request: Request, user_id: int) -> Response:
    """修改密码

    PUT /api/v2/users/{user_id}/change_password

    权限：仅本人。修改他人密码一律 403（管理员改密码走 reset_password）。
    这是有意的契约收紧：旧实现允许任何已认证用户修改任意用户密码。
    """
    if not getattr(request.user, "id", None) or request.user.id != user_id:
        return ApiResponse.error(
            code=ErrorCode.NOT_FOUND,
            message="只能修改自己的密码",
            http_status_code=403,
        )
    serializer = ChangePasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        ok = UserService.change_password(
            user_id=user_id,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    if not ok:
        return ApiResponse.error(code=ErrorCode.PASSWORD_INCORRECT, message="旧密码错误")
    return ApiResponse.success(message="密码修改成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def reset_password(request: Request, user_id: int) -> Response:
    """重置密码（管理员用）

    PUT /api/v2/users/{user_id}/reset_password
    """
    serializer = ResetPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        affected = UserService.reset_password(
            user_id=user_id,
            new_password=serializer.validated_data["new_password"],
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data={"affected": affected}, message="密码重置成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def disable_user(request: Request, user_id: int) -> Response:
    """禁用用户

    PUT /api/v2/users/{user_id}/disable
    """
    serializer = IdSerializer(data={"id": user_id})
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = UserService.disable_user(user_id)
    return ApiResponse.success(data={"affected": affected}, message="禁用成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def enable_user(request: Request, user_id: int) -> Response:
    """启用用户

    PUT /api/v2/users/{user_id}/enable
    """
    serializer = IdSerializer(data={"id": user_id})
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = UserService.enable_user(user_id)
    return ApiResponse.success(data={"affected": affected}, message="启用成功")


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def delete_user(request: Request, user_id: int) -> Response:
    """删除用户

    DELETE /api/v2/users/{user_id}/delete
    """
    serializer = IdSerializer(data={"id": user_id})
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = UserService.delete_user(user_id)
    return ApiResponse.success(data={"affected": affected}, message="删除成功")
