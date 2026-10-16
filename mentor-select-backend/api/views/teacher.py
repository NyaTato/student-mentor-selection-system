"""teacher_view - 导师接口

数据源：canonical `apps.teachers.TeacherProfile`（主键 = user_id）。
ID 契约（v2）：响应中的 `id` 与 `user_id` 均为 canonical user_id。

权限策略：
- 查询接口（get/list/by_user/by_number）: IsAuthenticated
  导师公开目录（list/by_number）对已认证用户保持开放，不因手机号收紧而受限
- 写操作（create/update/delete）: IsAdmin
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from api.schema import (
    IdSerializer,
    TeacherCreateSerializer,
    TeacherListQuerySerializer,
    TeacherUpdateSerializer,
)
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.response import ApiResponse
from constant.error_code import ErrorCode
from lib.service.teacher_service import TeacherService


def _teacher_to_dict(teacher) -> dict:
    """TeacherProfile 对象转 dict

    canonical 主键即 user_id，故 id 与 user_id 输出同一值。
    """
    if teacher is None:
        return None
    return {
        "id": teacher.pk,
        "user_id": teacher.user_id,
        "teacher_number": teacher.teacher_number,
        "name": teacher.name,
        "college": teacher.college,
        "title": teacher.title,
        "research_area": teacher.research_area,
        "profile": teacher.profile,
        "graduation_direction": teacher.graduation_direction,
        "thesis_topic": teacher.thesis_topic,
        "student_requirement": teacher.student_requirement,
        "created_at": teacher.created_at,
        "updated_at": teacher.updated_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_teacher(request: Request, teacher_id: int) -> Response:
    """获取导师信息

    GET /api/v2/teachers/{teacher_id}
    """
    teacher = TeacherService.get_teacher(teacher_id)
    if teacher is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="导师不存在", http_status_code=404)
    return ApiResponse.success(data=_teacher_to_dict(teacher), message="查询成功")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_teacher_by_user_id(request: Request, user_id: int) -> Response:
    """根据 user_id 获取导师档案

    GET /api/v2/teachers/by_user/{user_id}
    """
    teacher = TeacherService.get_by_user_id(user_id)
    if teacher is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="导师档案不存在", http_status_code=404)
    return ApiResponse.success(data=_teacher_to_dict(teacher), message="查询成功")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_teacher_by_teacher_number(request: Request, teacher_number: str) -> Response:
    """根据工号获取导师

    GET /api/v2/teachers/by_number/{teacher_number}
    """
    teacher = TeacherService.get_by_teacher_number(teacher_number)
    if teacher is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="导师不存在", http_status_code=404)
    return ApiResponse.success(data=_teacher_to_dict(teacher), message="查询成功")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_teachers(request: Request) -> Response:
    """查询导师列表（分页）

    GET /api/v2/teachers/list?page=1&page_size=20
    """
    serializer = TeacherListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    result = TeacherService.list_teachers(
        page=serializer.validated_data["page"],
        page_size=serializer.validated_data["page_size"],
    )
    result["list"] = [_teacher_to_dict(t) for t in result["list"]]
    return ApiResponse.success(data=result, message="查询成功")


@api_view(["POST"])
@permission_classes([IsAdmin])
def create_teacher(request: Request) -> Response:
    """创建导师（同时创建 User 和 Teacher）

    POST /api/v2/teachers/create
    """
    serializer = TeacherCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        result = TeacherService.create_teacher(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            teacher_number=serializer.validated_data["teacher_number"],
            name=serializer.validated_data["name"],
            college=serializer.validated_data["college"],
            title=serializer.validated_data.get("title", ""),
            research_area=serializer.validated_data.get("research_area", ""),
            profile=serializer.validated_data.get("profile"),
            graduation_direction=serializer.validated_data.get("graduation_direction"),
            thesis_topic=serializer.validated_data.get("thesis_topic"),
            student_requirement=serializer.validated_data.get("student_requirement"),
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data=result, message="创建成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def update_teacher(request: Request, teacher_id: int) -> Response:
    """更新导师信息

    PUT /api/v2/teachers/{teacher_id}/update
    """
    serializer = TeacherUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = TeacherService.update_teacher(teacher_id, **serializer.validated_data)
    return ApiResponse.success(data={"affected": affected}, message="更新成功")


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def delete_teacher(request: Request, teacher_id: int) -> Response:
    """删除导师

    DELETE /api/v2/teachers/{teacher_id}/delete
    """
    serializer = IdSerializer(data={"id": teacher_id})
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = TeacherService.delete_teacher(teacher_id)
    return ApiResponse.success(data={"affected": affected}, message="删除成功")
