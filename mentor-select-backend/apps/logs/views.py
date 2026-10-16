"""
日志管理视图

操作日志和登录日志均为只读，由系统内部写入。
"""
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.viewsets import ReadOnlyApiResponseViewSet
from apps.logs.serializers import LoginLogSerializer, OperationLogSerializer
from apps.logs.services import LoginLogService, OperationLogService

operation_log_service = OperationLogService()
login_log_service = LoginLogService()


@extend_schema_view(
    list=extend_schema(tags=["日志管理"], summary="查询操作日志列表"),
    retrieve=extend_schema(tags=["日志管理"], summary="查询单个操作日志"),
)
class OperationLogViewSet(ReadOnlyApiResponseViewSet):
    """操作日志 ViewSet（只读）"""

    queryset = operation_log_service.repository.get_queryset()
    serializer_class = OperationLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """安全要求：操作日志含全站操作轨迹（可能间接包含个人数据线索），
        查询接口收紧为仅管理员（原先对任意登录用户开放）。"""
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        """支持按 user / academic_year / action / target_type / target_id 过滤"""
        queryset = self.queryset
        user = self.request.query_params.get("user")
        academic_year = self.request.query_params.get("academic_year")
        action = self.request.query_params.get("action")
        target_type = self.request.query_params.get("target_type")
        target_id = self.request.query_params.get("target_id")
        if user:
            queryset = queryset.filter(user_id=user)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if action:
            queryset = queryset.filter(action=action)
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        return queryset


@extend_schema_view(
    list=extend_schema(tags=["日志管理"], summary="查询登录日志列表"),
    retrieve=extend_schema(tags=["日志管理"], summary="查询单个登录日志"),
)
class LoginLogViewSet(ReadOnlyApiResponseViewSet):
    """登录日志 ViewSet（只读）"""

    queryset = login_log_service.repository.get_queryset()
    serializer_class = LoginLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """安全要求：登录日志含用户名与登录轨迹，查询接口收紧为仅管理员。"""
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        """支持按 user / username / is_success 过滤"""
        queryset = self.queryset
        user = self.request.query_params.get("user")
        username = self.request.query_params.get("username")
        is_success = self.request.query_params.get("is_success")
        if user:
            queryset = queryset.filter(user_id=user)
        if username:
            queryset = queryset.filter(username__icontains=username)
        if is_success is not None:
            if is_success.lower() in ("true", "1"):
                queryset = queryset.filter(is_success=True)
            elif is_success.lower() in ("false", "0"):
                queryset = queryset.filter(is_success=False)
        return queryset
