"""
学年管理路由
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AcademicYearViewSet

router = DefaultRouter()
router.register(r"", AcademicYearViewSet, basename="academic-year")

urlpatterns = [
    path("", include(router.urls)),
]
