"""
用户管理路由
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminProfileViewSet, UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"admin-profiles", AdminProfileViewSet, basename="admin-profile")

urlpatterns = [
    path("", include(router.urls)),
]
