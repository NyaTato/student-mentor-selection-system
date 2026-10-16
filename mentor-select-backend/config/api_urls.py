"""
API URL 路由汇总
所有 App 的 API 路由在这里汇总
"""
from django.urls import include, path

urlpatterns = [
    # 认证
    path("auth/", include("apps.users.urls_auth")),
    # 用户管理
    path("", include("apps.users.urls")),
    path("students/", include("apps.students.urls")),
    path("teachers/", include("apps.teachers.urls")),
    path("applications/", include("apps.applications.urls")),
    path("assignments/", include("apps.assignments.urls")),
    path("announcements/", include("apps.announcements.urls")),
    path("academic-years/", include("apps.academic_year.urls")),
    path("imports/", include("apps.imports.urls")),
    path("system/", include("apps.system.urls")),
    path("logs/", include("apps.logs.urls")),
    path("statistics/", include("apps.statistics.urls")),
]
