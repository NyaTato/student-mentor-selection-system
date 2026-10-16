"""
学生管理视图

权限（v2 业务闭环，角色裁剪）：
- 管理员：全部学生读写
- 学生：只能读取自己的档案
- 导师：只能读取「与自己存在真实申请或录取关系」的学生（需指定 academic_year），
  避免通过列表接口批量拉取全部学生数据
"""
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.common.enums import UserRole
from apps.common.permissions import IsAdmin, IsAuthenticated
from apps.common.query_params import (
    StudentDirectoryQuerySerializer,
    parse_query,
)
from apps.common.viewsets import BaseApiResponseViewSet
from apps.students.serializers import (
    StudentProfileCreateSerializer,
    StudentProfileSerializer,
    StudentProfileUpdateSerializer,
)
from apps.students.services import StudentProfileService

student_profile_service = StudentProfileService()


@extend_schema_view(
    list=extend_schema(tags=["学生管理"], summary="查询学生档案列表"),
    retrieve=extend_schema(tags=["学生管理"], summary="查询单个学生档案"),
    create=extend_schema(tags=["学生管理"], summary="创建学生档案"),
    update=extend_schema(tags=["学生管理"], summary="更新学生档案"),
    partial_update=extend_schema(tags=["学生管理"], summary="部分更新学生档案"),
    destroy=extend_schema(tags=["学生管理"], summary="删除学生档案"),
)
class StudentProfileViewSet(BaseApiResponseViewSet):
    """学生档案 ViewSet"""

    queryset = student_profile_service.repository.get_queryset()
    serializer_class = StudentProfileSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_permissions(self):
        """读接口对已认证用户开放（按角色裁剪范围），写接口仅管理员。"""
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        """角色裁剪 + 支持按 keyword / major / class_name 过滤"""
        queryset = self.queryset
        user = self.request.user
        role = getattr(user, "role", None)
        data = parse_query(StudentDirectoryQuerySerializer, self.request.query_params)
        academic_year_id = data.get("academic_year")

        if role == UserRole.STUDENT.value:
            # 学生只能看自己
            queryset = queryset.filter(user_id=user.id)
        elif role == UserRole.TEACHER.value:
            # 导师只能看：本学年向自己提交过申请的学生，或已录取到自己名下的学生
            if not academic_year_id:
                return queryset.none()
            queryset = queryset.filter(
                Q(
                    applications__teacher_id=user.id,
                    applications__academic_year_id=academic_year_id,
                )
                | Q(
                    admissions__teacher_id=user.id,
                    admissions__academic_year_id=academic_year_id,
                )
            ).distinct()
        # 管理员看全部

        keyword = data.get("keyword")
        major = data.get("major")
        class_name = data.get("class_name")

        if keyword:
            # 关键字匹配学号或姓名
            queryset = queryset.filter(
                Q(student_number__icontains=keyword) | Q(name__icontains=keyword)
            )
        if major:
            queryset = queryset.filter(major__icontains=major)
        if class_name:
            queryset = queryset.filter(class_name__icontains=class_name)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return StudentProfileCreateSerializer
        if self.action in ("update", "partial_update"):
            return StudentProfileUpdateSerializer
        return StudentProfileSerializer

    def perform_create(self, serializer):
        instance = student_profile_service.create(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = student_profile_service.update(
            serializer.instance.user_id, serializer.validated_data
        )
        serializer.instance = instance

    def perform_destroy(self, instance):
        student_profile_service.delete(instance.user_id)
