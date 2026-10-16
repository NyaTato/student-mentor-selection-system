"""导入管理路由"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ImportErrorReportView,
    ExcelTemplateView,
    ExcelUploadView,
    ImportLogViewSet,
    ImportTaskViewSet,
)

router = DefaultRouter()
router.register(r"tasks", ImportTaskViewSet, basename="import-task")
router.register(r"logs", ImportLogViewSet, basename="import-log")

urlpatterns = [
    # Excel 上传 + 导入
    path("upload/", ExcelUploadView.as_view(), name="import-upload"),
    # Excel 模板下载
    path("template/", ExcelTemplateView.as_view(), name="import-template"),
    # 导入错误报告下载
    path(
        "tasks/<int:task_id>/error-report/",
        ImportErrorReportView.as_view(),
        name="import-error-report",
    ),
    # 任务和日志的 RESTful 路由
    path("", include(router.urls)),
]
