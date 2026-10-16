"""本地隔离演示配置（local demo only, never production）。

用途：给浏览器人工验证用的最小可运行后端，不依赖 MySQL / Redis / RabbitMQ。
本文件显式覆盖 base.py 从 .env 读入的全部外部服务配置，因此即使本地存在
生产 .env（含真实 DB / Redis / JWT 密钥），演示进程也不会触碰它们。

隔离要点（按 Task 04 要求）：
- SQLite 文件固定为 ``<backend>/work/demo.sqlite3``，Django CACHES 为 LocMemCache，
  Celery 为 eager + memory broker/results，不连接任何外部服务。
- ``SECRET_KEY`` 仅取 ``DEMO_SECRET_KEY``，未设置则按进程随机生成；
  绝不继承 base 的 ``SECRET_KEY`` / ``JWT_SIGNING_KEY``；
  ``SIMPLE_JWT['SIGNING_KEY']`` 显式回指演示密钥，演示签发的 JWT 永不使用生产密钥。
- 原生 Redis 客户端配置指向不可用的本地端口（127.0.0.1:1, DB 15），
  需要真实 Redis 的状态自动推进/自动分配在最小演示中不可用，不做任何伪实现。
- ``DEBUG=False``，``ALLOWED_HOSTS`` 仅 localhost / 127.0.0.1 / testserver，
  请勿以 ``0.0.0.0`` 对外暴露；CORS 仅放行本地 3000 端口前端。
- 演示专用密码哈希沿用 PBKDF2，绝不使用 test.py 的 MD5 快速哈希。
- ``TESTING=True`` 供 monitoring 跳过 OTEL 初始化；同时强制 ``OTEL_ENABLED=false``。

运行（迁移由 Codex 在外部单独执行，本文件不执行任何 DB 操作）：
    python manage.py migrate --settings=config.settings.demo
    python manage.py seed_demo --settings=config.settings.demo [--password ...]
    python manage.py runserver 127.0.0.1:8000 --settings=config.settings.demo
"""

import os
import secrets
from pathlib import Path

from .base import *  # noqa: F401, F403
from .base import BASE_DIR  # noqa: F401

# ===== 演示模式标记（seed_demo 守卫依赖此标志）=====
DEMO_MODE = True

# 本配置明确不是生产配置，禁止复用于任何生产部署。
DEMO_IS_PRODUCTION = False

# 避免 monitoring / tracing 初始化外部 OTEL（apps.monitoring.apps 识别 TESTING）。
TESTING = True
os.environ.setdefault("OTEL_ENABLED", "false")
OTEL_ENABLED = False

DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# ===== 演示密钥：仅 DEMO_SECRET_KEY 或按进程随机生成 =====
_demo_secret = os.environ.get("DEMO_SECRET_KEY", "")
if not _demo_secret.strip():
    _demo_secret = secrets.token_urlsafe(48)

SECRET_KEY = _demo_secret

# 关键隔离：在 base 已从 .env 导入之后，强制把 JWT 签名密钥指回演示密钥，
# 永不继承生产 .env 中的 JWT_SIGNING_KEY / SECRET_KEY。
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405
SIMPLE_JWT["VERIFYING_KEY"] = None  # noqa: F405

# ===== 隔离数据库：固定 SQLite 文件，忽略 base .env 中的 MySQL 配置 =====
DEMO_DB_PATH = BASE_DIR / "work" / "demo.sqlite3"
DEMO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DEMO_DB_PATH),
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
    }
}

# ===== 缓存：本地内存，永不连接 Redis =====
CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "demo",
    }
}

# ===== 原生 Redis 客户端隔离：指向不可用端口，演示永不触碰真实服务/缓存/锁 =====
REDIS_HOST = "127.0.0.1"  # noqa: F405
REDIS_PORT = 1  # noqa: F405
REDIS_PASSWORD = ""  # noqa: F405
REDIS_DB = 15  # noqa: F405
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"  # noqa: F405

# ===== Celery：eager 同步 + 纯内存，不依赖 RabbitMQ/Redis =====
CELERY_TASK_ALWAYS_EAGER = True  # noqa: F405
CELERY_TASK_EAGER_PROPAGATES = True  # noqa: F405
CELERY_BROKER_URL = "memory://"  # noqa: F405
CELERY_RESULT_BACKEND = "cache+memory://"  # noqa: F405
CELERY_BEAT_SCHEDULE = {}  # noqa: F405

# ===== 密码哈希：显式使用 PBKDF2，禁止 test.py 的 MD5 快速哈希 =====
PASSWORD_HASHERS = [  # noqa: F405
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# 保留 base 的密码强度校验器（演示也不放宽）。
# AUTH_PASSWORD_VALIDATORS 沿用 base，不在此覆盖。

# ===== CORS：仅本地 3000 端口前端 =====
CORS_ALLOW_ALL_ORIGINS = False  # noqa: F405
CORS_ALLOWED_ORIGINS = [  # noqa: F405
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True  # noqa: F405

# CSRF 仅信任本地演示来源（Django 4+ 需要 scheme）。
CSRF_TRUSTED_ORIGINS = [  # noqa: F405
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# 演示日志保持克制，避免输出环境细节。
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "INFO"  # noqa: F405
LOGGING["loggers"]["django.db.backends"]["level"] = "WARNING"  # noqa: F405

# 确保 work 目录存在说明：不在 settings import 时创建任何文件/目录，
# ``work/demo.sqlite3`` 由 migrate 在外部命令中生成。
DEMO_DB_RELATIVE = str(Path("work") / "demo.sqlite3")
