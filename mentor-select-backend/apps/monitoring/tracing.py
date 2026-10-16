"""OpenTelemetry 分布式追踪初始化

在 Django / Celery 启动时自动配置 OpenTelemetry SDK：
- Tracer Provider（OTLP Exporter → otel-collector）
- Resource（service.name / namespace / version / environment）
- Auto Instrumentation：Django / Requests / Redis / DBAPI / Celery / Logging

设计要点：
- 通过 OTEL_ENABLED 环境变量控制启用 / 禁用
- 本地开发（无 otel-collector）设置 OTEL_ENABLED=false
- 幂等：多次调用不会重复初始化
- 异常安全：初始化失败不影响应用启动
- 与现有 TraceIDMiddleware 协同：OpenTelemetry 的 trace_id 自动注入日志

调用方式：
- Django：apps.monitoring.apps.MonitoringConfig.ready() 中调用
- Celery：worker_process_init 信号中调用
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 幂等标志
_initialized: bool = False


def is_tracing_enabled() -> bool:
    """检查 OpenTelemetry 分布式追踪是否启用

    Returns:
        True 表示启用
    """
    return os.environ.get("OTEL_ENABLED", "false").lower() == "true"


def _get_resource() -> Any:
    """构建 OpenTelemetry Resource（服务标识）

    Returns:
        Resource 实例
    """
    from opentelemetry.sdk.resources import Resource

    service_name = os.environ.get("OTEL_SERVICE_NAME", "mentor-backend")
    resource_attrs = os.environ.get(
        "OTEL_RESOURCE_ATTRIBUTES",
        "service.namespace=mentor-match,service.version=1.0.0,deployment.environment=production",
    )

    # 解析 OTEL_RESOURCE_ATTRIBUTES（key=value,key=value 格式）
    attributes: dict[str, str] = {"service.name": service_name}
    for attr in resource_attrs.split(","):
        attr = attr.strip()
        if "=" in attr:
            key, value = attr.split("=", 1)
            attributes[key.strip()] = value.strip()

    return Resource.create(attributes)


def _setup_tracer_provider() -> None:
    """配置 Tracer Provider 和 OTLP Exporter"""
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"
    )
    # OTLP HTTP Span Exporter 端点为 /v1/traces
    if not endpoint.endswith("/v1/traces"):
        span_endpoint = f"{endpoint}/v1/traces"
    else:
        span_endpoint = endpoint

    resource = _get_resource()
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=span_endpoint)
    processor = BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        export_timeout_millis=30_000,
        schedule_delay_millis=5000,
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


def _setup_auto_instrumentation() -> None:
    """启用所有 Auto Instrumentation

    自动采集：
    - Django：HTTP Request / Response / Template / Middleware
    - Requests：HTTP Client 调用
    - Redis：GET / SET / DEL / EXPIRE 等操作
    - DBAPI：SQL 查询（mysqlclient / MySQLdb）
    - Celery：Task 发送 / 执行
    - Logging：日志注入 trace_id / span_id
    """
    # Django Instrumentation
    try:
        from opentelemetry.instrumentation.django import DjangoInstrumentor

        DjangoInstrumentor().instrument()
        logger.info("OpenTelemetry Django instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument Django: %s", e)

    # Requests Instrumentation（HTTP Client）
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        logger.info("OpenTelemetry Requests instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument Requests: %s", e)

    # Redis Instrumentation
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
        logger.info("OpenTelemetry Redis instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument Redis: %s", e)

    # DBAPI Instrumentation（mysqlclient / MySQLdb）
    # mysqlclient 提供 MySQLdb 模块，兼容 DBAPI 2.0
    # 使用 trace_integration API（DatabaseApiIntegration.wrap 在 0.50+ 已移除）
    try:
        import MySQLdb  # type: ignore[import-untyped]
        from opentelemetry.instrumentation.dbapi import (
            trace_integration,
        )

        trace_integration(MySQLdb, "connect", "mysql")
        logger.info("OpenTelemetry DBAPI (MySQLdb) instrumentation enabled")
    except ImportError:
        # mysqlclient 未安装（如 SQLite 开发环境），跳过
        logger.debug("MySQLdb not available, skipping DBAPI instrumentation")
    except Exception as e:
        logger.warning("Failed to instrument DBAPI: %s", e)

    # Celery Instrumentation
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
        logger.info("OpenTelemetry Celery instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument Celery: %s", e)

    # Logging Instrumentation
    # 自动在 LogRecord 中注入 otelTraceID / otelSpanID / otelServiceName
    try:
        from opentelemetry.instrumentation.logging import (
            LoggingInstrumentor,
        )

        LoggingInstrumentor().instrument(
            set_logging_format=True,
            log_level=logging.INFO,
        )
        logger.info("OpenTelemetry Logging instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument Logging: %s", e)


def initialize_tracing() -> None:
    """初始化 OpenTelemetry 分布式追踪

    在 Django AppConfig.ready() 或 Celery worker_process_init 中调用。
    幂等：多次调用不会重复初始化。

    环境变量：
    - OTEL_ENABLED：true / false（默认 false）
    - OTEL_SERVICE_NAME：服务名称
    - OTEL_EXPORTER_OTLP_ENDPOINT：OTLP 端点
    - OTEL_RESOURCE_ATTRIBUTES：资源属性
    """
    global _initialized

    if _initialized:
        return

    if not is_tracing_enabled():
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED=false)")
        _initialized = True
        return

    try:
        _setup_tracer_provider()
        _setup_auto_instrumentation()
        _initialized = True
        logger.info(
            "OpenTelemetry tracing initialized (service=%s, endpoint=%s)",
            os.environ.get("OTEL_SERVICE_NAME", "mentor-backend"),
            os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"),
        )
    except Exception as e:
        # 初始化失败不影响应用启动
        logger.error("Failed to initialize OpenTelemetry tracing: %s", e, exc_info=True)
        _initialized = True  # 标记已尝试，避免重复失败
