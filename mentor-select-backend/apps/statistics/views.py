"""统计视图

提供 Dashboard、申请、录取、导师名额使用情况统计 API。

权限：管理员
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.common.error_codes import ErrorCode
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.query_params import AcademicYearQuerySerializer, parse_query
from apps.common.response import ApiResponse
from apps.statistics.services import StatisticsService

statistics_service = StatisticsService()


def _require_academic_year(request):
    """安全解析 academic_year 查询参数（非法输入 -> 400，而非 500）

    Returns:
        (academic_year_id, error_response)；error_response 不为 None 时应直接返回。
    """
    data = parse_query(AcademicYearQuerySerializer, request.query_params)
    academic_year_id = data.get("academic_year")
    if not academic_year_id:
        return None, ApiResponse.error(
            code=ErrorCode.PARAM_MISSING, message="缺少 academic_year 参数"
        )
    return academic_year_id, None


class DashboardStatisticsView(APIView):
    """Dashboard 统计

    GET /api/v1/statistics/dashboard/?academic_year=1
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["统计分析"],
        summary="Dashboard 统计",
        parameters=[
            OpenApiParameter(
                name="academic_year",
                description="学年 ID",
                required=True,
                type=int,
            )
        ],
    )
    def get(self, request):
        academic_year_id, error = _require_academic_year(request)
        if error is not None:
            return error

        data = statistics_service.get_dashboard(academic_year_id)
        return ApiResponse.success(data=data, message="查询成功")


class ApplicationStatisticsView(APIView):
    """申请统计

    GET /api/v1/statistics/applications/?academic_year=1
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["统计分析"],
        summary="申请统计",
        parameters=[
            OpenApiParameter(
                name="academic_year",
                description="学年 ID",
                required=True,
                type=int,
            )
        ],
    )
    def get(self, request):
        academic_year_id, error = _require_academic_year(request)
        if error is not None:
            return error

        data = statistics_service.get_applications_statistics(academic_year_id)
        return ApiResponse.success(data=data, message="查询成功")


class AdmissionStatisticsView(APIView):
    """录取统计

    GET /api/v1/statistics/admissions/?academic_year=1
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["统计分析"],
        summary="录取统计",
        parameters=[
            OpenApiParameter(
                name="academic_year",
                description="学年 ID",
                required=True,
                type=int,
            )
        ],
    )
    def get(self, request):
        academic_year_id, error = _require_academic_year(request)
        if error is not None:
            return error

        data = statistics_service.get_admissions_statistics(academic_year_id)
        return ApiResponse.success(data=data, message="查询成功")


class TeacherQuotaStatisticsView(APIView):
    """导师名额使用情况统计

    GET /api/v1/statistics/teachers/?academic_year=1
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["统计分析"],
        summary="导师名额使用情况统计",
        parameters=[
            OpenApiParameter(
                name="academic_year",
                description="学年 ID",
                required=True,
                type=int,
            )
        ],
    )
    def get(self, request):
        academic_year_id, error = _require_academic_year(request)
        if error is not None:
            return error

        data = statistics_service.get_teachers_quota_statistics(academic_year_id)
        return ApiResponse.success(data=data, message="查询成功")
