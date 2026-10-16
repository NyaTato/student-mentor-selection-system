"""
基础 ViewSet
统一 CRUD 响应格式，使用 Service / Repository 模式。

子类应通过 self.service 访问业务逻辑，避免直接操作 ORM。
若子类未提供 service，则回退到默认的 ModelViewSet 行为（保持向后兼容）。
"""
from django.utils import timezone
from rest_framework import mixins, viewsets

from apps.common.response import ApiResponse


class BaseApiResponseViewSet(viewsets.ModelViewSet):
    """统一 API 响应 ViewSet 基类

    自动将 CRUD 操作的响应包装为 ApiResponse 格式：
    {code: 0, message: "success", data: {...}}

    perform_destroy 默认软删除：如果模型有 deleted_at 字段则软删除，
    否则硬删除。

    子类可通过设置 service 属性启用 Service/Repository 模式：
        class MyViewSet(BaseApiResponseViewSet):
            service = MyService()
            serializer_class = MySerializer
    """

    service = None  # 可选：Service 实例

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # DRF paginate_queryset 返回 list，真正的 Page 对象在 self.paginator.page
            return ApiResponse.paginated(
                serializer.data, self.paginator.page, message="查询成功"
            )
        serializer = self.get_serializer(queryset, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return ApiResponse.created(data=serializer.data, message="创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return ApiResponse.success(data=serializer.data, message="更新成功")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return ApiResponse.success(message="删除成功")

    def perform_destroy(self, instance):
        # 软删除：如果模型有 deleted_at 字段则软删除，否则硬删除
        if hasattr(instance, "deleted_at"):
            instance.deleted_at = timezone.now()
            update_fields = ["deleted_at", "updated_at"]
            if hasattr(instance, "version"):
                instance.version = (instance.version or 0) + 1
                update_fields.append("version")
            instance.save(update_fields=update_fields)
        else:
            instance.delete()


class ReadOnlyApiResponseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """只读 ViewSet 基类

    仅提供 list 和 retrieve 操作，响应统一包装为 ApiResponse 格式。
    """

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return ApiResponse.paginated(
                serializer.data, self.paginator.page, message="查询成功"
            )
        serializer = self.get_serializer(queryset, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data, message="查询成功")
