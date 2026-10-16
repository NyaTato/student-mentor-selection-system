"""导入管理视图

提供：
- ImportTaskViewSet: 导入任务查询 + 错误报告下载
- ImportLogViewSet: 导入日志查询（只读）
- ExcelUploadView: Excel 文件上传 + 导入
- ExcelTemplateView: Excel 导入模板下载
"""
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema, extend_schema_view
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from urllib.parse import quote

from apps.common.enums import UserRole
from apps.common.error_codes import ErrorCode
from apps.common.permissions import IsAdmin
from apps.common.response import ApiResponse
from apps.common.viewsets import ReadOnlyApiResponseViewSet
from apps.imports.serializers import (
    ExcelUploadSerializer,
    ImportLogSerializer,
    ImportTaskSerializer,
)
from apps.imports.services import (
    ExcelImportService,
    ImportLogService,
    ImportTaskService,
)

import_task_service = ImportTaskService()
import_log_service = ImportLogService()
excel_import_service = ExcelImportService()


@extend_schema_view(
    list=extend_schema(tags=["导入管理"], summary="查询导入任务列表"),
    retrieve=extend_schema(tags=["导入管理"], summary="查询单个导入任务"),
)
class ImportTaskViewSet(ReadOnlyApiResponseViewSet):
    """导入任务 ViewSet（只读 + 错误报告下载）"""

    queryset = import_task_service.repository.get_queryset()
    serializer_class = ImportTaskSerializer
    # 安全要求：导入任务/日志包含原始 Excel 来源数据（可能含个人隐私），
    # 查询接口仅管理员可用（原先对任意登录用户开放）。
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        """支持按 academic_year / status / role 过滤"""
        queryset = self.queryset
        academic_year = self.request.query_params.get("academic_year")
        status_param = self.request.query_params.get("status")
        role = self.request.query_params.get("role")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if role:
            queryset = queryset.filter(role=role)
        return queryset


@extend_schema_view(
    list=extend_schema(tags=["导入管理"], summary="查询导入日志列表"),
    retrieve=extend_schema(tags=["导入管理"], summary="查询单个导入日志"),
)
class ImportLogViewSet(ReadOnlyApiResponseViewSet):
    """导入日志 ViewSet（只读）"""

    queryset = import_log_service.repository.get_queryset()
    serializer_class = ImportLogSerializer
    # 同上：导入日志可能包含原始来源的个人数据，仅管理员可查询。
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        """支持按 task / status 过滤"""
        queryset = self.queryset
        task = self.request.query_params.get("task")
        status_param = self.request.query_params.get("status")
        if task:
            queryset = queryset.filter(task_id=task)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset


class ExcelUploadView(APIView):
    """Excel 文件上传 + 导入

    POST /api/v1/imports/upload/
    Content-Type: multipart/form-data
    Body: file, role, academic_year
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["导入管理"],
        summary="上传 Excel 文件并执行导入",
        request=ExcelUploadSerializer,
        responses={201: ImportTaskSerializer},
    )
    def post(self, request):
        serializer = ExcelUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file = serializer.validated_data["file"]
        role = serializer.validated_data["role"]
        academic_year_id = serializer.validated_data["academic_year"]

        # 读取文件内容
        file_content = file.read()
        file_name = file.name
        file_size = file.size

        # 执行导入
        task = excel_import_service.upload_and_import(
            file_content=file_content,
            file_name=file_name,
            file_size=file_size,
            role=role,
            academic_year_id=academic_year_id,
            triggered_by=request.user,
        )

        # 返回任务详情
        task_serializer = ImportTaskSerializer(task)
        return ApiResponse.created(
            data=task_serializer.data, message="导入完成"
        )


class ExcelTemplateView(APIView):
    """Excel 导入模板下载

    GET /api/v1/imports/template/?role=1
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["导入管理"],
        summary="下载 Excel 导入模板",
        parameters=[],
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request):
        role = int(request.query_params.get("role", 0))
        if role not in (
            UserRole.STUDENT.value,
            UserRole.TEACHER.value,
            UserRole.ADMIN.value,
        ):
            return ApiResponse.error(
                code=ErrorCode.PARAM_INVALID,
                message="role 参数必须是 1(学生)、2(导师) 或 3(管理员)",
            )

        content = excel_import_service.generate_template(role)

        role_names = {
            UserRole.STUDENT.value: "student",
            UserRole.TEACHER.value: "teacher",
            UserRole.ADMIN.value: "admin",
        }
        role_names_cn = {
            UserRole.STUDENT.value: "学生",
            UserRole.TEACHER.value: "导师",
            UserRole.ADMIN.value: "管理员",
        }
        ascii_filename = f"{role_names[role]}_template.xlsx"
        utf8_filename = f"{role_names_cn[role]}导入模板.xlsx"

        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        # RFC 5987 编码：ASCII fallback + UTF-8 filename*
        response["Content-Disposition"] = (
            f"attachment; filename=\"{ascii_filename}\"; "
            f"filename*=UTF-8''{quote(utf8_filename)}"
        )
        return response


class ImportErrorReportView(APIView):
    """导入错误报告下载

    GET /api/v1/imports/tasks/{task_id}/error-report/
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["导入管理"],
        summary="下载导入错误报告",
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request, task_id):
        content = excel_import_service.generate_error_report(task_id)
        ascii_filename = f"error_report_task{task_id}.xlsx"
        utf8_filename = f"导入错误报告_task{task_id}.xlsx"

        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        # RFC 5987 编码：ASCII fallback + UTF-8 filename*
        response["Content-Disposition"] = (
            f"attachment; filename=\"{ascii_filename}\"; "
            f"filename*=UTF-8''{quote(utf8_filename)}"
        )
        return response
