"""
学年管理视图
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action

from apps.academic_year.serializers import (
    AcademicYearSerializer,
    AcademicYearUpdateSerializer,
)
from apps.academic_year.services import AcademicYearService
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.response import ApiResponse
from apps.common.viewsets import BaseApiResponseViewSet

academic_year_service = AcademicYearService()


@extend_schema_view(
    list=extend_schema(tags=["学年管理"], summary="查询学年列表"),
    retrieve=extend_schema(tags=["学年管理"], summary="查询单个学年"),
    create=extend_schema(tags=["学年管理"], summary="创建学年"),
    update=extend_schema(tags=["学年管理"], summary="更新学年"),
    partial_update=extend_schema(tags=["学年管理"], summary="部分更新学年"),
    destroy=extend_schema(tags=["学年管理"], summary="删除学年"),
)
class AcademicYearViewSet(BaseApiResponseViewSet):
    """学年 ViewSet"""

    queryset = academic_year_service.repository.get_queryset()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """查询接口（list/retrieve/active）对所有登录用户开放，
        写操作（create/update/destroy/activate/close）保持 IsAdmin。"""
        if self.action in ("list", "retrieve", "active"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        """支持按 status 过滤"""
        queryset = self.queryset
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return AcademicYearUpdateSerializer
        return AcademicYearSerializer

    def perform_create(self, serializer):
        instance = academic_year_service.create(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = academic_year_service.update(
            serializer.instance.id, serializer.validated_data
        )
        serializer.instance = instance

    def perform_destroy(self, instance):
        academic_year_service.delete(instance.id)

    @extend_schema(
        tags=["学年管理"],
        summary="激活学年",
        responses={200: AcademicYearSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, *args, **kwargs):
        """激活学年（自动归档当前激活的学年）"""
        instance = self.get_object()
        instance = academic_year_service.activate(instance.id)
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="激活成功")

    @extend_schema(
        tags=["学年管理"],
        summary="关闭学年",
        responses={200: AcademicYearSerializer},
    )
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs):
        """关闭学年（归档）"""
        instance = self.get_object()
        instance = academic_year_service.close(instance.id)
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="关闭成功")

    @extend_schema(
        tags=["学年管理"],
        summary="查询当前激活学年",
        responses={200: AcademicYearSerializer},
    )
    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request, *args, **kwargs):
        """查询当前激活的学年"""
        instance = academic_year_service.get_active()
        if instance is None:
            return ApiResponse.success(data=None, message="当前无激活学年")
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="查询成功")
