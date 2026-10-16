"""统计路由"""
from django.urls import path

from .views import (
    AdmissionStatisticsView,
    ApplicationStatisticsView,
    DashboardStatisticsView,
    TeacherQuotaStatisticsView,
)

urlpatterns = [
    path("dashboard/", DashboardStatisticsView.as_view(), name="stats-dashboard"),
    path(
        "applications/",
        ApplicationStatisticsView.as_view(),
        name="stats-applications",
    ),
    path(
        "admissions/",
        AdmissionStatisticsView.as_view(),
        name="stats-admissions",
    ),
    path(
        "teachers/",
        TeacherQuotaStatisticsView.as_view(),
        name="stats-teachers",
    ),
]
