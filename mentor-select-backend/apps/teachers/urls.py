"""
导师管理路由
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TeacherProfileViewSet, TeacherQuotaViewSet

router = DefaultRouter()
router.register(
    r"profiles", TeacherProfileViewSet, basename="teacher-profile"
)
router.register(r"quotas", TeacherQuotaViewSet, basename="teacher-quota")

urlpatterns = [
    path("", include(router.urls)),
]
