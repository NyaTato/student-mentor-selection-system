"""
生产环境配置
"""
import os

from .base import *  # noqa: F401, F403
from .key_guard import validate_production_keys

DEBUG = False

# 过滤空字符串，避免 ALLOWED_HOSTS=[""] 允许空 Host 头
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]

# ===== 启动密钥强度校验（拒绝空/短/默认/示例值）=====
# 读取**原始环境变量**而非 base 里 fallback 后的默认值，以便区分
# 「未设置」与「显式设置了弱值」两种错误；不读取/打印任何 .env 内容。
_secret_key_env = os.environ.get("SECRET_KEY")
_jwt_signing_key_env = os.environ.get("JWT_SIGNING_KEY")

validate_production_keys(_secret_key_env, _jwt_signing_key_env)

# JWT 签名密钥：显式配置时使用显式值（已校验），否则回退到已校验的 SECRET_KEY
if _jwt_signing_key_env and _jwt_signing_key_env.strip():
    SIMPLE_JWT["SIGNING_KEY"] = _jwt_signing_key_env  # noqa: F405
else:
    SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

# 安全设置
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# SSL 重定向通过环境变量控制：nginx 配置 HTTPS 时启用，纯 HTTP 环境禁用
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "same-origin"
# Nginx 反向代理后信任 X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 生产环境关闭 Swagger
SPECTACULAR_SETTINGS["SERVE_INCLUDE_SCHEMA"] = False  # noqa: F405

# 生产环境日志级别
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "INFO"  # noqa: F405
