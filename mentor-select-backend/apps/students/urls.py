"""
学生管理路由
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StudentProfileViewSet

router = DefaultRouter()
router.register(
    r"profiles", StudentProfileViewSet, basename="student-profile"
)

urlpatterns = [
    path("", include(router.urls)),
]
