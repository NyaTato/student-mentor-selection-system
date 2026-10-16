"""统计应用配置"""
from django.apps import AppConfig


class StatisticsConfig(AppConfig):
    """统计应用配置"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.statistics"
    verbose_name = "统计分析"
