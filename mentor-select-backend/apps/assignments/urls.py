"""分配结果路由"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdmissionViewSet,
    AutoAssignmentLogViewSet,
    AutoAssignmentView as AutoAssignmentPreviewView,
    AutoAssignmentRevokeView,
    AutoAssignmentRunView,
    ManualAssignView,
)

router = DefaultRouter()
router.register(r"admissions", AdmissionViewSet, basename="admission")
router.register(
    r"auto-logs", AutoAssignmentLogViewSet, basename="auto-assignment-log"
)

urlpatterns = [
    # 管理员人工分配（持久化）；v1 保留同一别名，v2 为正式入口
    path(
        "manual-assign/",
        ManualAssignView.as_view(),
        name="manual-assign",
    ),
    # 自动分配操作端点
    path(
        "auto-assign/preview/",
        AutoAssignmentPreviewView.as_view(),
        name="auto-assign-preview",
    ),
    path(
        "auto-assign/run/",
        AutoAssignmentRunView.as_view(),
        name="auto-assign-run",
    ),
    path(
        "auto-assign/revoke/",
        AutoAssignmentRevokeView.as_view(),
        name="auto-assign-revoke",
    ),
    # 任务和日志的 RESTful 路由
    path("", include(router.urls)),
]
