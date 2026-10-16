"""
公告管理视图
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action

from apps.announcements.serializers import (
    AnnouncementCreateSerializer,
    AnnouncementSerializer,
    AnnouncementUpdateSerializer,
)
from apps.announcements.services import AnnouncementService
from apps.common.enums import UserRole
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.query_params import (
    AnnouncementListQuerySerializer,
    parse_query,
)
from apps.common.response import ApiResponse
from apps.common.viewsets import BaseApiResponseViewSet

announcement_service = AnnouncementService()


@extend_schema_view(
    list=extend_schema(tags=["公告管理"], summary="查询公告列表"),
    retrieve=extend_schema(tags=["公告管理"], summary="查询单个公告"),
    create=extend_schema(tags=["公告管理"], summary="创建公告"),
    update=extend_schema(tags=["公告管理"], summary="更新公告"),
    partial_update=extend_schema(tags=["公告管理"], summary="部分更新公告"),
    destroy=extend_schema(tags=["公告管理"], summary="删除公告"),
)
class AnnouncementViewSet(BaseApiResponseViewSet):
    """公告 ViewSet"""

    queryset = announcement_service.repository.get_queryset()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """查询接口（list/retrieve）对所有登录用户开放，
        写操作（create/update/destroy/publish/unpublish）保持 IsAdmin。"""
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        """支持按 academic_year / is_published 过滤

        安全要求：非管理员**只能**看到已发布公告。
        即使显式请求 `?is_published=false`，也会被强制为 True，
        避免未发布（草稿）公告通过查询参数泄漏给普通用户。
        （retrieve 同样走 get_queryset，故未发布公告的详情也不可见。）
        """
        queryset = self.queryset
        data = parse_query(AnnouncementListQuerySerializer, self.request.query_params)
        academic_year_id = data.get("academic_year")
        is_published = data.get("is_published")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        is_admin = getattr(self.request.user, "role", None) == UserRole.ADMIN.value
        if not is_admin:
            return queryset.filter(is_published=True)

        if is_published is not None:
            queryset = queryset.filter(is_published=is_published)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        if self.action in ("update", "partial_update"):
            return AnnouncementUpdateSerializer
        return AnnouncementSerializer

    def perform_create(self, serializer):
        # 自动填充 created_by
        data = dict(serializer.validated_data)
        data["created_by"] = self.request.user
        instance = announcement_service.create(data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = announcement_service.update(
            serializer.instance.id, serializer.validated_data
        )
        serializer.instance = instance

    def perform_destroy(self, instance):
        announcement_service.delete(instance.id)

    @extend_schema(
        tags=["公告管理"],
        summary="发布公告",
        responses={200: AnnouncementSerializer},
    )
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, *args, **kwargs):
        """发布公告"""
        instance = self.get_object()
        instance = announcement_service.publish(instance.id)
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="发布成功")

    @extend_schema(
        tags=["公告管理"],
        summary="取消发布公告",
        responses={200: AnnouncementSerializer},
    )
    @action(detail=True, methods=["post"], url_path="unpublish")
    def unpublish(self, request, *args, **kwargs):
        """取消发布公告"""
        instance = self.get_object()
        instance = announcement_service.unpublish(instance.id)
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="取消发布成功")
