"""student_view - 学生接口

数据源：canonical `apps.students.StudentProfile`（主键 = user_id）。
ID 契约（v2）：响应中的 `id` 与 `user_id` 均为 canonical user_id。

权限策略：
- 查询接口（get/list/by_user/by_number）: IsAuthenticated + **角色裁剪**（见下）
- update_student_phone: IsAuthenticated（学生改自己电话；本人校验在 Service/View 层）
- 写操作（create/update/delete）: IsAdmin

记录级权限（收紧：整条记录而非单个字段）：
- 管理员：全部学生
- 学生：仅本人档案
- 导师：仅「与自己存在真实申请或录取关系」的学生
- 匿名 / 其它角色：拒绝（401/403）；范围内查不到一律 404

裁剪在 `StudentDB.visible_queryset` 完成，再交给 View 格式化输出，
因此 `phone`、`name`、`student_number` 等字段随整条记录一并裁剪
（未授权用户看不到记录，而非「看得到记录但 phone 为 null」）。
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from api.schema import (
    IdSerializer,
    StudentCreateSerializer,
    StudentListQuerySerializer,
    StudentPhoneUpdateSerializer,
    StudentUpdateSerializer,
)
from apps.common.enums import UserRole
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.response import ApiResponse
from constant.error_code import ErrorCode
from lib.service.student_service import StudentService


def _student_to_dict(student) -> dict:
    """StudentProfile 转 dict

    canonical 主键即 user_id，因此 id 与 user_id 输出同一个值。
    角色裁剪已在 Service/DB 层完成（不可见的记录根本不会传到这里）。
    """
    if student is None:
        return None
    return {
        "id": student.pk,
        "user_id": student.user_id,
        "student_number": student.student_number,
        "name": student.name,
        "major": student.major,
        "class_name": student.class_name,
        "department": student.department,
        "phone": student.phone,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_student(request: Request, student_id: int) -> Response:
    """获取学生信息

    GET /api/v2/students/{student_id}
    """
    student = StudentService.get_student(student_id, actor=request.user)
    if student is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="学生不存在", http_status_code=404)
    return ApiResponse.success(
        data=_student_to_dict(student),
        message="查询成功",
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_student_by_user_id(request: Request, user_id: int) -> Response:
    """根据 user_id 获取学生档案

    GET /api/v2/students/by_user/{user_id}
    """
    student = StudentService.get_by_user_id(user_id, actor=request.user)
    if student is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="学生档案不存在", http_status_code=404)
    return ApiResponse.success(
        data=_student_to_dict(student),
        message="查询成功",
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_student_by_student_number(request: Request, student_number: str) -> Response:
    """根据学号获取学生

    GET /api/v2/students/by_number/{student_number}
    """
    student = StudentService.get_by_student_number(student_number, actor=request.user)
    if student is None:
        return ApiResponse.error(code=ErrorCode.NOT_FOUND, message="学生不存在", http_status_code=404)
    return ApiResponse.success(
        data=_student_to_dict(student),
        message="查询成功",
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_students(request: Request) -> Response:
    """查询学生列表（分页，按角色裁剪后再分页）

    GET /api/v2/students/list?page=1&page_size=20
    """
    serializer = StudentListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    result = StudentService.list_students(
        page=serializer.validated_data["page"],
        page_size=serializer.validated_data["page_size"],
        actor=request.user,
    )
    result["list"] = [_student_to_dict(s) for s in result["list"]]
    return ApiResponse.success(data=result, message="查询成功")


@api_view(["POST"])
@permission_classes([IsAdmin])
def create_student(request: Request) -> Response:
    """创建学生（同时创建 canonical User 和 StudentProfile）

    POST /api/v2/students/create

    响应 data: {"user_id": <canonical user_id>, "student_id": <同一 user_id>}
    """
    serializer = StudentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        result = StudentService.create_student(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            student_number=serializer.validated_data["student_number"],
            name=serializer.validated_data["name"],
            major=serializer.validated_data["major"],
            class_name=serializer.validated_data["class_name"],
            phone=serializer.validated_data.get("phone"),
            department=serializer.validated_data.get("department"),
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data=result, message="创建成功")


@api_view(["PUT"])
@permission_classes([IsAdmin])
def update_student(request: Request, student_id: int) -> Response:
    """更新学生信息

    PUT /api/v2/students/{student_id}/update
    """
    serializer = StudentUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        affected = StudentService.update_student(student_id, **serializer.validated_data)
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data={"affected": affected}, message="更新成功")


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_student_phone(request: Request, student_id: int) -> Response:
    """更新学生电话（学生自助修改）

    PUT /api/v2/students/{student_id}/phone

    权限：仅学生本人或管理员（收紧：不允许任意已认证用户修改他人手机号）。
    """
    user = getattr(request, "user", None)
    is_self = getattr(user, "id", None) == student_id
    is_admin = user is not None and user.role == int(UserRole.ADMIN)
    if not (is_self or is_admin):
        return ApiResponse.error(
            code=ErrorCode.NOT_FOUND,
            message="只能修改自己的手机号",
            http_status_code=403,
        )
    serializer = StudentPhoneUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    try:
        affected = StudentService.update_phone(
            student_id=student_id,
            phone=serializer.validated_data["phone"],
        )
    except ValueError as e:
        return ApiResponse.error(code=ErrorCode.BUSINESS_ERROR, message=str(e))
    return ApiResponse.success(data={"affected": affected}, message="电话更新成功")


@api_view(["DELETE"])
@permission_classes([IsAdmin])
def delete_student(request: Request, student_id: int) -> Response:
    """删除学生（软删除，保留历史外键）

    DELETE /api/v2/students/{student_id}/delete
    """
    serializer = IdSerializer(data={"id": student_id})
    if not serializer.is_valid():
        return ApiResponse.error(code=ErrorCode.VALIDATION_ERROR, message="参数校验失败", data=serializer.errors)
    affected = StudentService.delete_student(student_id)
    return ApiResponse.success(data={"affected": affected}, message="删除成功")
