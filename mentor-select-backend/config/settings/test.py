"""
测试环境配置
使用 SQLite 内存数据库，避免依赖 MySQL/Redis/RabbitMQ
"""
from .base import *  # noqa: F401, F403
from .base import BASE_DIR  # noqa: F401

# 测试环境标志（跳过 OpenTelemetry 初始化等耗时操作）
TESTING = True

DEBUG = False
ALLOWED_HOSTS = ["*"]

# 测试使用 SQLite 内存数据库
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# 测试使用本地内存缓存
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test",
    }
}

# 测试环境禁用密码验证器（加快测试速度）
AUTH_PASSWORD_VALIDATORS = []

# 测试环境使用更快的密码哈希
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# 测试环境日志级别
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["django.db.backends"]["level"] = "WARNING"  # noqa: F405

# Celery 测试：使用 eager 模式（同步执行，不依赖 RabbitMQ）
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
