"""
日志管理路由
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LoginLogViewSet, OperationLogViewSet

router = DefaultRouter()
router.register(r"operation", OperationLogViewSet, basename="operation-log")
router.register(r"login", LoginLogViewSet, basename="login-log")

urlpatterns = [
    path("", include(router.urls)),
]
