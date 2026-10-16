"""Django AppConfig for monitoring app"""
from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    """监控应用配置

    在 ready() 中初始化 OpenTelemetry 分布式追踪。
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.monitoring"
    verbose_name = "监控"

    def ready(self) -> None:
        """Django 启动时初始化 OpenTelemetry

        幂等：多次调用安全。
        异常安全：初始化失败不影响应用启动。
        """
        # 避免在 makemigrations / migrate 等命令中初始化
        # 仅在 runserver / gunicorn / celery 中初始化
        from django.conf import settings

        # 测试环境跳过（避免 pytest 重复初始化）
        if getattr(settings, "TESTING", False):
            return

        try:
            from apps.monitoring.tracing import initialize_tracing

            initialize_tracing()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "OpenTelemetry initialization skipped: %s", e
            )
