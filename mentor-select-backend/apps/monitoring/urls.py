"""监控 URL 配置

仅暴露 /metrics 端点供 Prometheus 抓取。

使用 django_prometheus 提供的 URL 路由（pattern="metrics"），
metrics 实例由本 app 的 metrics/registry.py 自定义（基于 prometheus_client）。

最终 URL：/metrics
"""
from django.urls import include, path

urlpatterns = [
    # Prometheus metrics 抓取端点（/metrics）
    path("", include("django_prometheus.urls")),
]
