"""
开发环境配置
使用 Docker 提供的 MySQL / Redis / RabbitMQ
"""
from .base import *  # noqa: F401, F403
from .base import BASE_DIR  # noqa: F401

DEBUG = True

ALLOWED_HOSTS = ["*"]

# 开发环境允许所有 CORS
CORS_ALLOW_ALL_ORIGINS = True

# 开发环境日志级别
LOGGING["loggers"]["django"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # noqa: F405

# 开发环境显示 SQL 查询
LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["django.db.backends"]["propagate"] = True  # noqa: F405

# 开发环境若未启用 Redis，使用本地内存缓存（避免依赖 Redis 启动失败）
import os as _os
if not _os.environ.get("REDIS_HOST"):
    CACHES = {  # noqa: F405
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "dev",
        }
    }

# Celery 开发环境：若未启用 RabbitMQ，使用 eager 模式（同步执行，不依赖 broker）
if not _os.environ.get("CELERY_BROKER_URL") and not _os.environ.get("RABBITMQ_HOST"):
    CELERY_TASK_ALWAYS_EAGER = True  # noqa: F405
    CELERY_TASK_EAGER_PROPAGATES = True  # noqa: F405
    CELERY_BROKER_URL = "memory://"  # noqa: F405
    CELERY_RESULT_BACKEND = "cache+memory://"  # noqa: F405
    # 禁用 Beat 定时任务调度（避免尝试连接 broker）
    CELERY_BEAT_SCHEDULE = {}  # noqa: F405
