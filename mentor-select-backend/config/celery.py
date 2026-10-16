"""
Celery 配置
"""
import os

from celery import Celery
from celery.signals import worker_process_init

from apps.common.logger import get_logger

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("mentor_match")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

logger = get_logger("celery")


@worker_process_init.connect
def init_otel_on_worker(**kwargs) -> None:
    """Celery worker 进程启动时初始化 OpenTelemetry

    确保 Celery Task 的 Trace 能发送到 otel-collector。
    幂等：initialize_tracing() 内部有 _initialized 标志。
    """
    try:
        from apps.monitoring.tracing import initialize_tracing

        initialize_tracing()
    except Exception as e:
        logger.warning("OpenTelemetry initialization skipped on Celery worker: %s", e)


@app.task(bind=True)
def debug_task(self):
    logger.info("Request: %r", self.request)
