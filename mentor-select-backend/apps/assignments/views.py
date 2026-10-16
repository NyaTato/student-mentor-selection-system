"""分配结果视图

提供：
- AdmissionViewSet: 录取结果查询（只读，按角色裁剪范围）
- AutoAssignmentLogViewSet: 自动分配日志查询（只读，仅管理员）
- AutoAssignmentView / Run / Revoke: 自动分配操作（仅管理员）
- ManualAssignView: 管理员人工分配（持久化到 DB）

权限（v2 业务闭环）：
- 录取结果：学生只看自己 / 导师只看自己的 / 管理员全部
- 自动分配日志与录取日志：仅管理员
"""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.assignments.serializers import (
    AdmissionSerializer,
    AutoAssignmentLogSerializer,
    AutoAssignmentPreviewRequestSerializer,
    AutoAssignmentPreviewResponseSerializer,
    AutoAssignmentRevokeRequestSerializer,
    AutoAssignmentRevokeResponseSerializer,
    AutoAssignmentRunRequestSerializer,
    AutoAssignmentRunResponseSerializer,
    ManualAssignRequestSerializer,
)
from apps.assignments.services import (
    AdmissionService,
    AutoAssignmentLogService,
    AutoAssignmentService,
)
from apps.common.enums import UserRole
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.query_params import (
    AdmissionListQuerySerializer,
    AutoAssignmentLogListQuerySerializer,
    parse_query,
)
from apps.common.response import ApiResponse
from apps.common.viewsets import ReadOnlyApiResponseViewSet

admission_service = AdmissionService()
auto_assignment_log_service = AutoAssignmentLogService()
# AutoAssignmentService 全为 classmethod，无需实例化
AutoAssignService = AutoAssignmentService


@extend_schema_view(
    list=extend_schema(tags=["分配管理"], summary="查询录取结果列表"),
    retrieve=extend_schema(tags=["分配管理"], summary="查询单个录取结果"),
)
class AdmissionViewSet(ReadOnlyApiResponseViewSet):
    """录取结果 ViewSet（只读）

    录取结果由业务流程产生（申请通过 / 人工分配 / 自动分配），
    不通过 API 直接创建/修改/删除。

    权限范围（安全要求）：
    - 学生：只能看自己的录取结果
    - 导师：只能看自己名下的录取结果
    - 管理员：全部
    """

    queryset = admission_service.repository.get_queryset()
    serializer_class = AdmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """角色裁剪 + 按 academic_year / teacher / student 过滤"""
        queryset = self.queryset
        user = self.request.user
        data = parse_query(AdmissionListQuerySerializer, self.request.query_params)

        # 角色裁剪：不允许通过查询参数请求其它角色的完整数据
        if user.role == UserRole.STUDENT.value:
            queryset = queryset.filter(student_id=user.id)
        elif user.role == UserRole.TEACHER.value:
            queryset = queryset.filter(teacher_id=user.id)

        academic_year_id = data.get("academic_year")
        teacher = data.get("teacher")
        student = data.get("student")
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if teacher:
            queryset = queryset.filter(teacher_id=teacher)
        if student:
            queryset = queryset.filter(student_id=student)
        return queryset


@extend_schema_view(
    list=extend_schema(tags=["分配管理"], summary="查询自动分配日志列表"),
    retrieve=extend_schema(tags=["分配管理"], summary="查询单个自动分配日志"),
)
class AutoAssignmentLogViewSet(ReadOnlyApiResponseViewSet):
    """自动分配日志 ViewSet（只读，仅管理员）

    安全要求：自动分配日志暴露全学年分配明细（含未匹配学生统计），
    仅管理员可查询（原先对任意登录用户开放）。
    """

    queryset = auto_assignment_log_service.repository.get_queryset()
    serializer_class = AutoAssignmentLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        """支持按 academic_year / status / is_revoked 过滤"""
        queryset = self.queryset
        data = parse_query(
            AutoAssignmentLogListQuerySerializer, self.request.query_params
        )
        academic_year_id = data.get("academic_year")
        status = data.get("status")
        is_revoked = data.get("is_revoked")
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if status:
            queryset = queryset.filter(status=status)
        if is_revoked is not None:
            queryset = queryset.filter(is_revoked=is_revoked)
        return queryset

    @extend_schema(
        tags=["分配管理"],
        summary="查询某次自动分配的录取结果",
        responses={200: AdmissionSerializer},
    )
    @action(detail=True, methods=["get"], url_path="admissions")
    def admissions(self, request, pk=None):
        """查询某次自动分配产生的录取结果"""
        log = self.get_object()
        admissions = admission_service.list_by_academic_year(
            log.academic_year_id
        ).filter(auto_assignment_log_id=log.id)
        serializer = AdmissionSerializer(admissions, many=True)
        return ApiResponse.success(data=serializer.data, message="查询成功")


class AutoAssignmentView(APIView):
    """自动分配操作视图

    提供三个端点：
    - POST /api/v1/assignments/auto-assign/preview/ — 预览分配（不获取锁、不创建数据）
    - POST /api/v1/assignments/auto-assign/run/ — 执行分配（支持 dry_run 参数）
    - POST /api/v1/assignments/auto-assign/revoke/ — 撤销分配
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["分配管理"],
        summary="预览自动分配结果",
        request=AutoAssignmentPreviewRequestSerializer,
        responses={200: AutoAssignmentPreviewResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        """预览自动分配结果（不实际执行分配）"""
        serializer = AutoAssignmentPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        academic_year_id = serializer.validated_data["academic_year"]

        result = AutoAssignService.preview(academic_year_id=academic_year_id)
        return ApiResponse.success(data=result, message="预览成功")


class AutoAssignmentRunView(APIView):
    """执行自动分配视图

    POST /api/v1/assignments/auto-assign/run/
    Body: {"academic_year": int, "dry_run": bool}
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["分配管理"],
        summary="执行自动分配",
        request=AutoAssignmentRunRequestSerializer,
        responses={200: AutoAssignmentRunResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        """执行自动分配（支持 dry_run 参数）"""
        serializer = AutoAssignmentRunRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        academic_year_id = serializer.validated_data["academic_year"]
        dry_run = serializer.validated_data.get("dry_run", False)

        result = AutoAssignService.run(
            academic_year_id=academic_year_id,
            triggered_by=request.user.id,
            dry_run=dry_run,
        )

        response_data = {
            "log_id": result.log_id,
            "total_unassigned": result.total_unassigned,
            "assigned_count": result.assigned_count,
            "failed_count": result.failed_count,
            "is_dry_run": result.is_dry_run,
            "is_all_assigned": result.is_all_assigned,
            "previews": [
                {
                    "student_id": p.student_id,
                    "student_name": p.student_name,
                    "student_number": p.student_number,
                    "teacher_id": p.teacher_id,
                    "teacher_name": p.teacher_name,
                    "teacher_number": p.teacher_number,
                    "remaining_quota": p.remaining_quota,
                }
                for p in result.previews
            ],
        }
        message = "Dry Run 完成" if dry_run else "自动分配完成"
        return ApiResponse.success(data=response_data, message=message)


class AutoAssignmentRevokeView(APIView):
    """撤销自动分配视图

    POST /api/v1/assignments/auto-assign/revoke/
    Body: {"academic_year": int, "auto_assignment_log": int}
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["分配管理"],
        summary="撤销自动分配",
        request=AutoAssignmentRevokeRequestSerializer,
        responses={200: AutoAssignmentRevokeResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        """撤销自动分配（删除 AUTO_ASSIGNED 来源的 admission）"""
        serializer = AutoAssignmentRevokeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        academic_year_id = serializer.validated_data["academic_year"]
        auto_assignment_log_id = serializer.validated_data["auto_assignment_log"]

        result = AutoAssignService.revoke(
            academic_year_id=academic_year_id,
            auto_assignment_log_id=auto_assignment_log_id,
            revoked_by=request.user.id,
        )
        return ApiResponse.success(data=result, message="撤销成功")


class ManualAssignView(APIView):
    """管理员人工分配视图（持久化）

    POST /api/v2/assignments/manual-assign/
    Body: {"academic_year": int, "student": int, "teacher": int}

    权限：显式 IsAdmin（人工分配是管理员专属能力）。
    校验：Serializer 负责字段类型/必填；Service 负责业务规则与事务；
    Repository 负责 DB 访问。
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        tags=["分配管理"],
        summary="管理员人工分配学生到导师（持久化）",
        request=ManualAssignRequestSerializer,
        responses={201: AdmissionSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = ManualAssignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        admission = admission_service.manual_assign(
            academic_year_id=data["academic_year"],
            student_id=data["student"],
            teacher_id=data["teacher"],
            operator_user=request.user,
        )
        result = AdmissionSerializer(admission)
        return ApiResponse.created(data=result.data, message="人工分配成功")
