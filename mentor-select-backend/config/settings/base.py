"""
Django 基础配置
所有环境共享的配置项
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 密钥
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-change-me-in-production-please",
)

# 调试模式
DEBUG = False

# 允许的主机
ALLOWED_HOSTS: list[str] = []

# Django Apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# 第三方 Apps
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
    "django_prometheus",
]

# 项目 Apps
LOCAL_APPS = [
    "apps.common",
    "apps.monitoring",
    "apps.users",
    "apps.students",
    "apps.teachers",
    "apps.applications",
    "apps.assignments",
    "apps.announcements",
    "apps.academic_year",
    "apps.imports",
    "apps.system",
    "apps.logs",
    "apps.statistics",
    "model",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# 中间件
MIDDLEWARE = [
    # 监控中间件（置于最外层，确保 TraceID 和计时覆盖全部后续中间件）
    "apps.monitoring.middleware.TraceIDMiddleware",
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Metrics 中间件（在 CommonMiddleware 之后，记录经规范化后的 path）
    "apps.monitoring.middleware.MetricsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

# URL 配置
ROOT_URLCONF = "config.urls"

# 模板
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# 数据库（支持 MySQL 和 SQLite，通过 DB_ENGINE 环境变量切换）
# CONN_MAX_AGE：复用 MySQL 连接 60 秒，避免每个请求新建/关闭连接导致连接数耗尽
# CONN_HEALTH_CHECKS：复用前检查连接健康，避免使用已断开的连接
_db_engine = os.environ.get("DB_ENGINE", "django.db.backends.mysql")
DATABASES = {
    "default": {
        "ENGINE": _db_engine,
        "NAME": os.environ.get("DB_NAME", "mentor_match"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "CONN_MAX_AGE": int(os.environ.get("CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
    }
}
# MySQL 专用选项
if _db_engine == "django.db.backends.mysql":
    DATABASES["default"]["OPTIONS"] = {"charset": "utf8mb4"}

# Redis 缓存
REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_DB = os.environ.get("REDIS_DB", "0")

REDIS_URL = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# RabbitMQ
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")

# Celery
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL",
    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}",
)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
)
CELERY_TIMEZONE = "Asia/Shanghai"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# 任务完成后才 ACK（默认为接收即 ACK），worker 崩溃时任务会重新入队，避免丢失
CELERY_TASK_ACKS_LATE = True
# worker 异常退出时拒绝（重新入队）任务，配合 ACKS_LATE 保证可靠性
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# 每个 worker 进程一次只预取 1 个任务，保证长任务（如自动分配）公平分发，避免单 worker 堆积
CELERY_WORKER_PREFETCH_COUNT = 1
# broker 连接重试：启动时若 RabbitMQ 不可用则重试，而非直接失败
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Celery Beat 定时任务（DATABASE.md 7.10：每分钟扫描自动状态切换）
CELERY_BEAT_SCHEDULE = {
    "check-and-progress-state": {
        "task": "system.check_and_progress_state",
        "schedule": 60.0,  # 每 60 秒执行一次
    },
}

# 认证
AUTH_USER_MODEL = "users.User"

# 密码验证
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# 密码哈希（PBKDF2）
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# 国际化
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

# 静态文件
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# 媒体文件
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# 默认主键字段
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF 配置
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
}

# SimpleJWT 配置
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_LIFETIME_DAYS", "7"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY", SECRET_KEY),
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# drf-spectacular 配置
SPECTACULAR_SETTINGS = {
    "TITLE": "学生选导师系统 API",
    "DESCRIPTION": "学生选导师系统后端 API 文档",
    "VERSION": "1.0.0",
    # 开发环境开放 Swagger / Schema；生产环境在 prod.py 中覆盖为 False
    "SERVE_INCLUDE_SCHEMA": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1/",
    "TAGS": [
        {"name": "认证", "description": "用户登录、登出、刷新 Token"},
        {"name": "用户管理", "description": "用户 CRUD 和个人信息"},
        {"name": "学生管理", "description": "学生档案 CRUD"},
        {"name": "导师管理", "description": "导师档案和名额 CRUD"},
        {"name": "学年管理", "description": "学年 CRUD"},
        {"name": "申请管理", "description": "学生申请、导师审核"},
        {"name": "分配管理", "description": "录取结果、自动分配（预览/执行/撤销）"},
        {"name": "公告管理", "description": "公告 CRUD"},
        {"name": "导入管理", "description": "Excel 导入、模板下载、错误报告"},
        {"name": "系统状态", "description": "状态机推进/回退、自动切换配置"},
        {"name": "日志管理", "description": "操作日志、登录日志查询"},
        {"name": "统计分析", "description": "Dashboard、申请、录取、导师名额统计"},
    ],
}

# CORS 配置
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

CORS_ALLOW_CREDENTIALS = True

# 日志配置
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "trace_id": {
            "()": "apps.monitoring.utils.trace.TraceIDLogFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} [trace:{trace_id}] [span:{span_id}] [duration:{duration}] {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["trace_id"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "filters": ["trace_id"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# 文件上传限制
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
