"""admin_view - 管理员接口

数据源：canonical `apps.users.AdminProfile`（主键 = user_id）+ canonical `apps.users.User`。
ID 契约（v2）：响应中的 `id` 与 `user_id` 均为 canonical user_id。

权限策略（收紧）：
- 查询接口（get/get_by_user_id/list）：IsAdmin
  管理员档案含账号用户名与账号元信息，旧实现允许任意已认证用户枚举，属越权读取。
- 写操作（create/update/delete）：IsAdmin
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from api.schema import (
    AdminCreateSerializer,
    AdminListQuerySerializer,
    AdminUpdateSerializer,
    IdSerializer,
)
from apps.common.permissions import IsAdmin
from apps.common.response import ApiResponse
from constant.error_code import ErrorCode
from lib.service.admin_service import AdminService
from lib.db_manager.user_db import UserDB


def _admin_to_dict(admin, user_map: dict | None = None) -> dict:
    """Admin 对象转 dict（包含 username 字段，避免前端用 name 兜底）

    Args:
        admin: Admin 对象
        user_map: 可选的 {user_id: username} 预取映射，避免 N+1 查询。
                  若为 None 则回退到单次查询（仅用于单条查询场景）。
    """
    if admin is None:
        return None
    # 优先从预取映射获取 username，避免 N+1 查询
    if user_map is not None:
        username = user_map.get(admin.user_id, "")
    else:
        user = UserDB.get_by_id(admin.user_id)
        username = user.username if user else ""
    return {
        "id": admin.pk,
        "user_id": admin.user_id,
        "username": username,
        "name": admin.name,
        "created_at": admin.created_at,
        "updated_at": admin.updated_at,
    }


@api_view(["GET"])
@permission_classes([IsAdmin])
def get_admin(request: Request, admin_id: int) -> Response:
    """获取管理员信息

    GET /api/v2/admins/{admin_id}

    权限：仅管理员
    """
    admin = AdminService.get_admin(admin_id)
    if admin is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="管理员不存在", http_status_code=404)
    return ApiResponse.success(data=_admin_to_dict(admin), message="查询成功")


@api_view(["GET"])
@permission_classes([IsAdmin])
def get_admin_by_user_id(request: Request, user_id: int) -> Response:
    """根据 user_id 获取管理员档案

    GET /api/v2/admins/by_user/{user_id}

    权限：仅管理员
    """
    admin = AdminService.get_by_user_id(user_id)
    if admin is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="管理员档案不存在", http_status_code=404)
    return ApiResponse.success(data=_admin_to_dict(admin), message="查询成功")


@api_view(["GET"])
@permission_classes([IsAdmin])
def list_admins(request: Request) -> Response:
    """查询管理员列表（分页）

    GET /api/v2/admins/list?page=1&page_size=20

    权限：仅管理员
    """
    serializer = AdminListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    result = AdminService.list_admins(
        page=serializer.validated_data["page"],
        page_size=serializer.validated_data["page_size"],
    )
    # 批量预取 User，避免 N+1 查询
    admins_list = result["list"]
    if admins_list:
        user_ids = [a.user_id for a in admins_list]
        users = UserDB.list_by_ids(user_ids)
        user_map = {u.id: u.username for u in users}
    else:
        user_map = {}
    result["list"] = [_admin_to_dict(a, user_map) for a in admins_list]
    return ApiResponse.success(data=result, message="查询成功")


@api_view(["POST"])
@permission_classes([IsAdmin])
def create_admin(request: Request) -> Response:
    """创建管理员（同时创建 User 和 Admin）

    POST /api/v2/admins/create
    """
    serializer = AdminCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        result = AdminService.create_admin(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            name=serializer.validated_data["name"],
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data=result, message="创建成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def update_admin(request: Request, admin_id: int) -> Response:
    """更新管理员信息

    PUT /api/v2/admins/{admin_id}/update
    """
    serializer = AdminUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = AdminService.update_admin(admin_id, **serializer.validated_data)
    return ApiResponse.success(data={"affected": affected}, message="更新成功")


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def delete_admin(request: Request, admin_id: int) -> Response:
    """删除管理员

    DELETE /api/v2/admins/{admin_id}/delete
    """
    serializer = IdSerializer(data={"id": admin_id})
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = AdminService.delete_admin(admin_id)
    return ApiResponse.success(data={"affected": affected}, message="删除成功")
