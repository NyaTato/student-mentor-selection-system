"""TraceID & Duration 工具

为每个请求生成 / 透传 trace_id，用于跨日志、metrics、链路追踪关联。
同时支持操作耗时（duration）的线程局部存储，供日志格式引用。

设计要点：
- 优先从上游 header X-Trace-ID 透传，保持链路完整
- 未携带则生成 UUID4（去除横线，便于日志检索）
- 使用 request._trace_id 属性存储（线程安全：每个请求对象独立）
- duration 通过线程局部存储传递，业务代码可通过 set_duration() 设置
"""
from __future__ import annotations

import threading
import uuid
from typing import Any

# 线程局部存储，用于在没有 request 上下文时也能获取当前 trace_id / duration
# 例如：Celery 任务、后台线程
_thread_local: threading.local = threading.local()


def generate_trace_id() -> str:
    """生成新的 trace_id

    使用 UUID4（随机），去除横线便于日志检索与显示。

    Returns:
        32 字符的十六进制字符串（无横线）
    """
    return uuid.uuid4().hex


def get_trace_id(request: Any | None = None) -> str:
    """获取当前请求的 trace_id

    优先级：
    1. request._trace_id（中间件已设置）
    2. request.META["HTTP_X_TRACE_ID"]（上游透传）
    3. 线程局部存储（无 request 上下文时）
    4. 生成新的 trace_id 并存入线程局部存储

    Args:
        request: Django HttpRequest 对象，可为 None

    Returns:
        trace_id 字符串
    """
    # 1. 从 request 属性获取
    if request is not None:
        trace_id = getattr(request, "_trace_id", None)
        if trace_id:
            return trace_id

        # 2. 从 header 获取
        trace_id = request.META.get("HTTP_X_TRACE_ID") if hasattr(request, "META") else None
        if trace_id:
            # 同步到 request 属性，便于后续直接获取
            set_trace_id(request, trace_id)
            return trace_id

    # 3. 从线程局部存储获取
    trace_id = getattr(_thread_local, "trace_id", None)
    if trace_id:
        return trace_id

    # 4. 生成新的 trace_id
    new_trace_id = generate_trace_id()
    _thread_local.trace_id = new_trace_id
    if request is not None:
        set_trace_id(request, new_trace_id)
    return new_trace_id


def set_trace_id(request: Any, trace_id: str) -> None:
    """将 trace_id 存储到 request 与线程局部存储

    Args:
        request: Django HttpRequest 对象
        trace_id: 要设置的 trace_id
    """
    if request is not None:
        request._trace_id = trace_id
        if hasattr(request, "META"):
            request.META["HTTP_X_TRACE_ID"] = trace_id
    # 同步到线程局部存储，便于在请求生命周期内的任意位置获取
    _thread_local.trace_id = trace_id


def clear_trace_id() -> None:
    """清除线程局部存储中的 trace_id

    在请求结束时调用，避免线程池复用时 trace_id 串号。
    """
    if hasattr(_thread_local, "trace_id"):
        del _thread_local.trace_id


def set_duration(duration: float) -> None:
    """设置当前操作的耗时到线程局部存储

    业务代码在完成耗时操作后调用此方法，后续日志将自动包含 duration 字段。

    Args:
        duration: 耗时（秒）
    """
    _thread_local.duration = f"{duration:.4f}s"


def clear_duration() -> None:
    """清除线程局部存储中的 duration

    在操作完成后调用，避免后续无关日志携带过期的 duration。
    """
    if hasattr(_thread_local, "duration"):
        del _thread_local.duration


class TraceIDLogFilter:
    """日志过滤器：将 trace_id / span_id / duration 注入日志记录

    优先级：
    1. OpenTelemetry 当前 Span Context（trace_id / span_id）
    2. 线程局部存储（trace_id / duration，由 TraceIDMiddleware 设置）

    在 LOGGING 配置中使用：
        "filters": {
            "trace_id": {"()": "apps.monitoring.utils.trace.TraceIDLogFilter"}
        }

    使用后日志格式可引用 {trace_id} / {span_id} / {duration}：
        "format": "[{asctime}] {levelname} {name} [trace:{trace_id}] [span:{span_id}] [duration:{duration}] {message}"
    """

    def filter(self, record) -> bool:
        """为日志记录添加 trace_id / span_id / duration 属性"""
        # 优先从 OpenTelemetry Span Context 获取（与 Jaeger 一致）
        span_ctx = _get_otel_span_context()
        record.trace_id = span_ctx.get("trace_id") or getattr(
            _thread_local, "trace_id", "-"
        )
        record.span_id = span_ctx.get("span_id", "-")
        record.duration = getattr(_thread_local, "duration", "-")
        return True


def _get_otel_span_context() -> dict[str, str]:
    """获取 OpenTelemetry 当前 Span Context（单一实现，供全项目复用）

    本函数是 Span Context 提取的唯一实现：
    - TraceIDLogFilter 通过它注入日志的 trace_id / span_id
    - get_otel_trace_id() 通过它获取 trace_id
    - TraceIDMiddleware 通过 get_otel_trace_id() 获取 trace_id

    Returns:
        包含 trace_id 和 span_id 的字典，无活跃 span 时返回空字典
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None:
            return {}

        context = span.get_span_context()
        if not context or not context.is_valid:
            return {}

        trace_id = f"{context.trace_id:032x}"
        span_id = f"{context.span_id:016x}"
        return {"trace_id": trace_id, "span_id": span_id}
    except Exception:
        return {}


def get_otel_trace_id() -> str | None:
    """从 OpenTelemetry Span Context 获取 trace_id

    供 TraceIDMiddleware 等只需要 trace_id 的场景使用，
    避免在各处重复实现 Span Context 提取逻辑。

    Returns:
        trace_id 字符串，无活跃 span 时返回 None
    """
    return _get_otel_span_context().get("trace_id")
