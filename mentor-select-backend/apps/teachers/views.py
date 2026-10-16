"""
导师管理视图
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.common.error_codes import ErrorCode
from apps.common.permissions import IsAdmin, IsAdminOrReadOnly, IsTeacher
from apps.common.query_params import AcademicYearQuerySerializer, parse_query
from apps.common.response import ApiResponse
from apps.common.viewsets import BaseApiResponseViewSet
from apps.teachers.serializers import (
    TeacherProfileCreateSerializer,
    TeacherProfileSerializer,
    TeacherProfileUpdateSerializer,
    TeacherQuotaBatchSerializer,
    TeacherQuotaSerializer,
)
from apps.teachers.services import TeacherProfileService, TeacherQuotaService

teacher_profile_service = TeacherProfileService()
teacher_quota_service = TeacherQuotaService()


@extend_schema_view(
    list=extend_schema(tags=["导师管理"], summary="查询导师档案列表"),
    retrieve=extend_schema(tags=["导师管理"], summary="查询单个导师档案"),
    create=extend_schema(tags=["导师管理"], summary="创建导师档案"),
    update=extend_schema(tags=["导师管理"], summary="更新导师档案"),
    partial_update=extend_schema(tags=["导师管理"], summary="部分更新导师档案"),
    destroy=extend_schema(tags=["导师管理"], summary="删除导师档案"),
)
class TeacherProfileViewSet(BaseApiResponseViewSet):
    """导师档案 ViewSet"""

    queryset = teacher_profile_service.repository.get_queryset()
    serializer_class = TeacherProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_queryset(self):
        """支持按 teacher_number / name / college / research_area 过滤"""
        queryset = self.queryset
        params = self.request.query_params
        keyword = params.get("keyword")
        college = params.get("college")
        research_area = params.get("research_area")

        if keyword:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(teacher_number__icontains=keyword) | Q(name__icontains=keyword)
            )
        if college:
            queryset = queryset.filter(college__icontains=college)
        if research_area:
            queryset = queryset.filter(research_area__icontains=research_area)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return TeacherProfileCreateSerializer
        if self.action in ("update", "partial_update"):
            return TeacherProfileUpdateSerializer
        return TeacherProfileSerializer

    def perform_create(self, serializer):
        instance = teacher_profile_service.create(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = teacher_profile_service.update(
            serializer.instance.user_id, serializer.validated_data
        )
        serializer.instance = instance

    def perform_destroy(self, instance):
        teacher_profile_service.delete(instance.user_id)

    @extend_schema(
        tags=["导师管理"],
        summary="查询当前登录导师的档案",
        responses={200: TeacherProfileSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated, IsTeacher],
        url_path="me",
    )
    def me(self, request, *args, **kwargs):
        """导师查看自己的档案"""
        profile = teacher_profile_service.get_by_user_id(request.user.id)
        serializer = self.get_serializer(profile)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    @extend_schema(
        tags=["导师管理"],
        summary="导师目录（含汇总名额，供学生选导师使用）",
        responses={200: dict},
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="directory",
    )
    def directory(self, request, *args, **kwargs):
        """导师目录：已认证即可访问（学生选导师必需）

        只暴露**汇总**名额信息（admitted_count / remaining_quota + max_quota），
        不包含任何学生明细（学生数量之外的个体信息一律不返回），
        用于前端按角色展示「剩余名额」。
        """
        data = parse_query(AcademicYearQuerySerializer, request.query_params)
        academic_year_id = data.get("academic_year")
        if not academic_year_id:
            return ApiResponse.error(
                code=ErrorCode.PARAM_MISSING, message="缺少 academic_year 参数"
            )

        quota_map = {
            row["teacher_id"]: row
            for row in teacher_quota_service.repository.list_with_remaining(
                academic_year_id
            )
        }

        payload = []
        for profile in teacher_profile_service.list():
            quota = quota_map.get(profile.user_id)
            payload.append({
                "teacher_id": profile.user_id,
                "teacher_number": profile.teacher_number,
                "name": profile.name,
                "college": profile.college,
                "title": profile.title,
                "research_area": profile.research_area,
                # 汇总名额：未配置名额 -> has_quota=False，remaining_quota=0（视为已关闭）
                "has_quota": quota is not None,
                "max_quota": quota["max_quota"] if quota else None,
                "admitted_count": quota["admitted_count"] if quota else 0,
                "remaining_quota": quota["remaining_quota"] if quota else 0,
            })
        return ApiResponse.success(data=payload, message="查询成功")


@extend_schema_view(
    list=extend_schema(tags=["导师管理"], summary="查询导师名额列表"),
    retrieve=extend_schema(tags=["导师管理"], summary="查询单个导师名额"),
    create=extend_schema(tags=["导师管理"], summary="创建导师名额"),
    update=extend_schema(tags=["导师管理"], summary="更新导师名额"),
    partial_update=extend_schema(tags=["导师管理"], summary="部分更新导师名额"),
    destroy=extend_schema(tags=["导师管理"], summary="删除导师名额"),
)
class TeacherQuotaViewSet(BaseApiResponseViewSet):
    """导师名额 ViewSet"""

    queryset = teacher_quota_service.repository.get_queryset()
    serializer_class = TeacherQuotaSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """查询接口（list/retrieve/by_year）对所有登录用户开放，
        写操作（create/update/destroy/batch_set）保持 IsAdmin。"""
        if self.action in ("list", "retrieve", "by_year"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    # 说明：查询接口对已认证用户开放是**有意的读契约**（学生选导师需要看到
    # 汇总剩余名额）；写操作（create/update/destroy/batch_set）严格保持 IsAdmin。

    def get_queryset(self):
        """支持按 academic_year / teacher 过滤"""
        queryset = self.queryset
        params = self.request.query_params
        academic_year = params.get("academic_year")
        teacher = params.get("teacher")

        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if teacher:
            queryset = queryset.filter(teacher_id=teacher)
        return queryset

    def perform_create(self, serializer):
        instance = teacher_quota_service.create(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = teacher_quota_service.update(
            serializer.instance.id, serializer.validated_data
        )
        serializer.instance = instance

    def perform_destroy(self, instance):
        teacher_quota_service.delete(instance.id)

    @extend_schema(
        tags=["导师管理"],
        summary="按学年查询所有导师名额",
        responses={200: TeacherQuotaSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="by-year/(?P<year_id>[0-9]+)",
    )
    def by_year(self, request, year_id=None, *args, **kwargs):
        """按学年查询所有导师名额"""
        quotas = teacher_quota_service.list_by_year(int(year_id))
        serializer = self.get_serializer(quotas, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    @extend_schema(
        tags=["导师管理"],
        summary="批量设置导师名额",
        request=TeacherQuotaBatchSerializer,
        responses={200: TeacherQuotaSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="batch",
        permission_classes=[IsAuthenticated, IsAdmin],
    )
    def batch_set(self, request, *args, **kwargs):
        """批量设置导师名额"""
        serializer = TeacherQuotaBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instances = teacher_quota_service.batch_set_quota(
            academic_year_id=serializer.validated_data["academic_year"],
            quotas=serializer.validated_data["quotas"],
        )
        result_serializer = TeacherQuotaSerializer(instances, many=True)
        return ApiResponse.success(
            data=result_serializer.data, message="批量设置成功"
        )
