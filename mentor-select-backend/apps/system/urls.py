"""
系统状态路由
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    StateHistoryViewSet,
    SystemStateScheduleViewSet,
    SystemStateViewSet,
)

router = DefaultRouter()
router.register(r"states", SystemStateViewSet, basename="system-state")
router.register(
    r"schedules", SystemStateScheduleViewSet, basename="system-state-schedule"
)
router.register(r"histories", StateHistoryViewSet, basename="state-history")

urlpatterns = [
    path("", include(router.urls)),
]
