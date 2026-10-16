"""
URL 路由配置
"""
from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    """健康检查端点（供 Docker HEALTHCHECK 与负载均衡使用）

    GET /api/v1/health/
    返回 200 + {"status": "ok"}
    """
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    # 健康检查
    path("api/v1/health/", health_check, name="health-check"),
    # API v1
    path("api/v1/", include("config.api_urls")),
    # API v2（User/Student/Teacher/Admin）
    # 使用 v2 前缀避免与现有 apps/* 路由冲突
    path("api/v2/", include("api.urls")),
    # Prometheus 指标抓取端点（/metrics/）
    # 仅供 Prometheus 抓取，生产环境需通过 Nginx 限制访问 IP
    path("", include("apps.monitoring.urls")),
]

# Swagger / OpenAPI Schema 仅在开发环境开放
# 生产环境 SPECTACULAR_SETTINGS["SERVE_INCLUDE_SCHEMA"]=False，不注册路由，避免暴露接口文档
if settings.SPECTACULAR_SETTINGS.get("SERVE_INCLUDE_SCHEMA", True):
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularSwaggerView,
    )

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]
