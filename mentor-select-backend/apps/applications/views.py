"""
申请管理视图

权限矩阵：
- 学生：提交申请、查看自己的申请
- 导师：查看收到的申请、审核申请（通过/拒绝/批量）、撤销第一轮录取
- 管理员：查看所有申请、审核申请

查询参数统一经 Serializer 校验（见 apps.common.query_params），
不再出现裸 int() 转换（非法输入由 500 变为 400）。
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action

from apps.applications.serializers import (
    ApplicationBatchActionSerializer,
    ApplicationCreateSerializer,
    ApplicationSerializer,
)
from apps.applications.services import ApplicationService
from apps.common.enums import UserRole
from apps.common.permissions import IsAuthenticated
from apps.common.query_params import (
    ApplicationListQuerySerializer,
    parse_query,
)
from apps.common.response import ApiResponse
from apps.common.viewsets import BaseApiResponseViewSet

application_service = ApplicationService()


@extend_schema_view(
    list=extend_schema(tags=["申请管理"], summary="查询申请列表"),
    retrieve=extend_schema(tags=["申请管理"], summary="查询单个申请"),
    create=extend_schema(tags=["申请管理"], summary="学生提交申请"),
)
class ApplicationViewSet(BaseApiResponseViewSet):
    """申请 ViewSet

    申请不可删除（业务规则 R2），故禁用 DELETE 方法。
    """

    queryset = application_service.repository.get_queryset()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    # 申请不可删除
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        """根据角色过滤（学生只看自己 / 导师只看自己收到的 / 管理员全部）"""
        user = self.request.user
        queryset = self.queryset
        data = parse_query(ApplicationListQuerySerializer, self.request.query_params)

        # 学生只能看自己的申请
        if user.role == UserRole.STUDENT.value:
            queryset = queryset.filter(student_id=user.id)
        # 导师只能看自己收到的申请
        elif user.role == UserRole.TEACHER.value:
            queryset = queryset.filter(teacher_id=user.id)
        # 管理员看所有

        # 通用过滤
        academic_year_id = data.get("academic_year")
        round_value = data.get("round")
        status = data.get("status")

        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if round_value:
            queryset = queryset.filter(round=round_value)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return ApplicationCreateSerializer
        return ApplicationSerializer

    def perform_create(self, serializer):
        # 学生提交申请时，student 字段自动填为当前用户
        validated_data = serializer.validated_data
        if self.request.user.role == UserRole.STUDENT.value:
            validated_data["student_id"] = self.request.user.id
            validated_data.pop("student", None)
        # 通过 Service 创建，Service 内部使用 Repository
        application = application_service.create(validated_data)
        # 使用 Repository 获取带 select_related 的实例
        serializer.instance = application_service.repository.get_by_id(application.id)

    @extend_schema(
        tags=["申请管理"],
        summary="学生查询自己的申请",
        responses={200: ApplicationSerializer},
    )
    @action(detail=False, methods=["get"], url_path="my")
    def my_applications(self, request, *args, **kwargs):
        """学生查询自己的申请"""
        data = parse_query(ApplicationListQuerySerializer, request.query_params)
        applications = application_service.list_my_applications(
            student_user_id=request.user.id,
            academic_year_id=data.get("academic_year"),
        )
        serializer = self.get_serializer(applications, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    @extend_schema(
        tags=["申请管理"],
        summary="导师查询收到的申请",
        responses={200: ApplicationSerializer},
    )
    @action(detail=False, methods=["get"], url_path="teacher")
    def teacher_applications(self, request, *args, **kwargs):
        """导师查询收到的申请"""
        data = parse_query(ApplicationListQuerySerializer, request.query_params)

        applications = application_service.list_teacher_applications(
            teacher_user_id=request.user.id,
            academic_year_id=data.get("academic_year"),
            round_value=data.get("round"),
            status=data.get("status"),
        )
        serializer = self.get_serializer(applications, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")

    @extend_schema(
        tags=["申请管理"],
        summary="通过申请",
        responses={200: ApplicationSerializer},
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, *args, **kwargs):
        """导师通过申请"""
        application = application_service.approve(
            application_id=kwargs.get("pk"),
            operator_user=request.user,
        )
        serializer = self.get_serializer(application)
        return ApiResponse.success(data=serializer.data, message="通过成功")

    @extend_schema(
        tags=["申请管理"],
        summary="拒绝申请",
        responses={200: ApplicationSerializer},
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, *args, **kwargs):
        """导师拒绝申请"""
        application = application_service.reject(
            application_id=kwargs.get("pk"),
            operator_user=request.user,
        )
        serializer = self.get_serializer(application)
        return ApiResponse.success(data=serializer.data, message="拒绝成功")

    @extend_schema(
        tags=["申请管理"],
        summary="批量通过申请",
        request=ApplicationBatchActionSerializer,
        responses={200: ApplicationSerializer},
    )
    @action(detail=False, methods=["post"], url_path="batch-approve")
    def batch_approve(self, request, *args, **kwargs):
        """批量通过申请"""
        serializer = ApplicationBatchActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        applications = application_service.batch_approve(
            application_ids=serializer.validated_data["application_ids"],
            operator_user=request.user,
        )
        result_serializer = self.get_serializer(applications, many=True)
        return ApiResponse.success(data=result_serializer.data, message="批量通过完成")

    @extend_schema(
        tags=["申请管理"],
        summary="批量拒绝申请",
        request=ApplicationBatchActionSerializer,
        responses={200: ApplicationSerializer},
    )
    @action(detail=False, methods=["post"], url_path="batch-reject")
    def batch_reject(self, request, *args, **kwargs):
        """批量拒绝申请"""
        serializer = ApplicationBatchActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        applications = application_service.batch_reject(
            application_ids=serializer.validated_data["application_ids"],
            operator_user=request.user,
        )
        result_serializer = self.get_serializer(applications, many=True)
        return ApiResponse.success(data=result_serializer.data, message="批量拒绝完成")

    @extend_schema(
        tags=["申请管理"],
        summary="导师撤销第一轮录取",
        request=None,
        responses={200: ApplicationSerializer},
    )
    @action(detail=True, methods=["post"], url_path="revoke-approval")
    def revoke_approval(self, request, *args, **kwargs):
        """R2-04: 导师在第一轮审核阶段撤销已通过的录取（持久化）

        仅做请求/响应转换，事务与业务规则全部在 ApplicationService 内。
        v1 / v2 复用同一 ViewSet，故两条前缀下均可用。
        """
        application = application_service.revoke_approval(
            application_id=kwargs.get("pk"),
            operator_user=request.user,
        )
        serializer = self.get_serializer(application)
        return ApiResponse.success(data=serializer.data, message="撤销成功")

    @extend_schema(
        tags=["申请管理"],
        summary="学生取消第二轮申请",
        responses={200: None},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs):
        """R3-06: 学生取消第二轮申请（释放名额）"""
        application_service.cancel_second_round(
            application_id=kwargs.get("pk"),
            operator_user=request.user,
        )
        return ApiResponse.success(message="取消成功")
