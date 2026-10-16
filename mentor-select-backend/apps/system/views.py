"""
系统状态视图

权限：
- 管理员：推进/回退状态、配置自动切换
- 其他已认证用户：查看状态、查看历史
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action

from apps.common.error_codes import ErrorCode
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.query_params import (
    AcademicYearIdSerializer,
    ToggleAutoSerializer,
    parse_body,
)
from apps.common.response import ApiResponse
from apps.common.viewsets import BaseApiResponseViewSet, ReadOnlyApiResponseViewSet
from apps.system.serializers import (
    StateHistorySerializer,
    StateTransitionSerializer,
    SystemStateScheduleSerializer,
    SystemStateSerializer,
)
from apps.system.services import (
    SystemStateScheduleService,
    SystemStateService,
)

system_state_service = SystemStateService()
schedule_service = SystemStateScheduleService()


@extend_schema_view(
    list=extend_schema(tags=["系统状态"], summary="查询系统状态列表"),
    retrieve=extend_schema(tags=["系统状态"], summary="查询单个系统状态"),
    create=extend_schema(tags=["系统状态"], summary="为学年初始化系统状态"),
)
class SystemStateViewSet(BaseApiResponseViewSet):
    """系统状态 ViewSet（不可删除）"""

    http_method_names = ["get", "post", "head", "options"]
    queryset = system_state_service.repository.get_queryset()
    serializer_class = SystemStateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        academic_year = self.request.query_params.get("academic_year")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset

    def get_permissions(self):
        if self.action in ("create", "forward", "rollback"):
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # 调用 init_for_academic_year
        academic_year_id = serializer.validated_data["academic_year"]
        if hasattr(academic_year_id, "id"):
            academic_year_id = academic_year_id.id
        instance = system_state_service.init_for_academic_year(academic_year_id)
        serializer.instance = instance

    @extend_schema(
        tags=["系统状态"],
        summary="状态推进",
        request=StateTransitionSerializer,
        responses={200: SystemStateSerializer},
    )
    @action(detail=False, methods=["post"], url_path="forward")
    def forward(self, request, *args, **kwargs):
        """管理员推进系统状态"""
        serializer = StateTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        state = system_state_service.forward(
            academic_year_id=serializer.validated_data["academic_year"],
            operator_user=request.user,
        )
        result = SystemStateSerializer(state)
        return ApiResponse.success(data=result.data, message="状态推进成功")

    @extend_schema(
        tags=["系统状态"],
        summary="状态回退",
        request=StateTransitionSerializer,
        responses={200: SystemStateSerializer},
    )
    @action(detail=False, methods=["post"], url_path="rollback")
    def rollback(self, request, *args, **kwargs):
        """管理员回退系统状态（需提供原因）"""
        serializer = StateTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        state = system_state_service.rollback(
            academic_year_id=serializer.validated_data["academic_year"],
            reason=serializer.validated_data.get("reason", ""),
            operator_user=request.user,
        )
        result = SystemStateSerializer(state)
        return ApiResponse.success(data=result.data, message="状态回退成功")

    @extend_schema(
        tags=["系统状态"],
        summary="按学年查询系统状态",
        responses={200: SystemStateSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"by-year/(?P<year_id>[0-9]+)",
    )
    def by_year(self, request, year_id=None, *args, **kwargs):
        """按学年查询系统状态"""
        state = system_state_service.get_by_academic_year(int(year_id))
        serializer = self.get_serializer(state)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    @extend_schema(
        tags=["系统状态"],
        summary="查询状态变更历史",
        responses={200: StateHistorySerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"histories/(?P<year_id>[0-9]+)",
    )
    def histories(self, request, year_id=None, *args, **kwargs):
        """查询指定学年的状态变更历史"""
        histories = system_state_service.list_histories(int(year_id))
        serializer = StateHistorySerializer(histories, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")


@extend_schema_view(
    list=extend_schema(tags=["系统状态"], summary="查询自动状态切换配置列表"),
    retrieve=extend_schema(tags=["系统状态"], summary="查询单个自动状态切换配置"),
    create=extend_schema(tags=["系统状态"], summary="创建自动状态切换配置"),
    update=extend_schema(tags=["系统状态"], summary="更新自动状态切换配置"),
    partial_update=extend_schema(tags=["系统状态"], summary="部分更新自动状态切换配置"),
)
class SystemStateScheduleViewSet(BaseApiResponseViewSet):
    """自动状态切换配置 ViewSet（不可删除）"""

    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = schedule_service.repository.get_queryset()
    serializer_class = SystemStateScheduleSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """查询接口（list/retrieve/next_transition）对所有登录用户开放，
        写操作（create/update/partial_update/toggle_auto/update_by_year）保持 IsAdmin。"""
        if self.action in ("list", "retrieve", "next_transition"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        queryset = self.queryset
        academic_year = self.request.query_params.get("academic_year")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset

    def perform_create(self, serializer):
        instance = schedule_service.create(serializer.validated_data)
        serializer.instance = instance

    @extend_schema(
        tags=["系统状态"],
        summary="启停自动切换",
        request={"academic_year": int, "enabled": bool},
        responses={200: SystemStateScheduleSerializer},
    )
    @action(detail=False, methods=["post"], url_path="toggle-auto")
    def toggle_auto(self, request, *args, **kwargs):
        """启停自动切换

        参数经 Serializer 校验（原先 int() 直接转换，非法输入会 500）。
        """
        data = parse_body(ToggleAutoSerializer, request.data)
        schedule = schedule_service.toggle_auto(
            data["academic_year"], data["enabled"]
        )
        serializer = self.get_serializer(schedule)
        return ApiResponse.success(data=serializer.data, message="切换成功")

    @extend_schema(
        tags=["系统状态"],
        summary="按学年更新调度配置",
        request=SystemStateScheduleSerializer,
        responses={200: SystemStateScheduleSerializer},
    )
    @action(detail=False, methods=["put", "patch"], url_path="update-by-year")
    def update_by_year(self, request, *args, **kwargs):
        """按学年更新调度配置

        Body: {"academic_year": int, "first_round_start_at": ..., ...}
        """
        academic_year = request.data.get("academic_year")
        if academic_year is None:
            return ApiResponse.error(
                code=ErrorCode.PARAM_MISSING,
                message="缺少 academic_year 参数",
            )
        # 安全解析学年 ID（非法输入 -> 400 而非 500）
        academic_year = parse_body(AcademicYearIdSerializer, {"academic_year": academic_year})[
            "academic_year"
        ]

        # 剔除 academic_year 字段，只保留可更新字段
        update_fields = {
            k: v
            for k, v in request.data.items()
            if k
            in (
                "first_round_start_at",
                "first_round_end_at",
                "teacher_review_end_at",
                "second_round_end_at",
                "auto_enabled",
            )
        }

        schedule = schedule_service.update_schedule(
            academic_year, update_fields
        )
        serializer = self.get_serializer(schedule)
        return ApiResponse.success(data=serializer.data, message="更新成功")

    @extend_schema(
        tags=["系统状态"],
        summary="查询下一次自动切换信息",
        responses={200: None},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"next-transition/(?P<year_id>[0-9]+)",
    )
    def next_transition(self, request, year_id=None, *args, **kwargs):
        """查询下一次自动切换信息"""
        info = schedule_service.get_next_transition(int(year_id))
        return ApiResponse.success(data=info, message="查询成功")


@extend_schema_view(
    list=extend_schema(tags=["系统状态"], summary="查询状态变更历史列表"),
    retrieve=extend_schema(tags=["系统状态"], summary="查询单个状态变更历史"),
)
class StateHistoryViewSet(ReadOnlyApiResponseViewSet):
    """状态变更历史 ViewSet（只读）"""

    queryset = system_state_service.history_repository.get_queryset()
    serializer_class = StateHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        academic_year = self.request.query_params.get("academic_year")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset
