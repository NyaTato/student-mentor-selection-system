"""TraceID 中间件

为每个请求注入 trace_id，并在响应头中返回，便于：
- 客户端在日志中关联请求
- 服务端跨日志 / metrics / 链路追踪关联
- 上游服务透传 trace_id 保持链路完整

与 OpenTelemetry 协同：
- 优先使用 OpenTelemetry Span Context 的 trace_id（与 Jaeger 一致）
- 若 OpenTelemetry 未启用，回退到 X-Trace-ID header 或生成 UUID4

顺序契约（Ordering Contract）：
- OpenTelemetry DjangoInstrumentor 包装 WSGI handler（在 Django 中间件栈之外）
- 因此 OTel Root Span 在任何 Django 中间件运行之前就已创建
- TraceIDMiddleware 位于 MIDDLEWARE 栈最外层（settings/base.py），确保第一个运行
- 当 OTel 启用时，get_otel_trace_id() 在此中间件中必定返回有效 trace_id
- 若 OTel 未启用（OTEL_ENABLED=false），回退到 X-Trace-ID header 或 UUID4
"""
from __future__ import annotations

from typing import Any, Callable

from apps.monitoring.utils.trace import (
    clear_duration,
    clear_trace_id,
    generate_trace_id,
    get_otel_trace_id,
    set_trace_id,
)


class TraceIDMiddleware:
    """TraceID 中间件

    处理流程：
    1. 优先从 OpenTelemetry Span Context 获取 trace_id（与 Jaeger 一致）
    2. 若无，从请求头 X-Trace-ID 获取上游 trace_id
    3. 若无，生成新的 trace_id
    4. 存入 request._trace_id 和 request.META
    5. 在响应头 X-Trace-ID 中返回
    6. 请求结束后清理线程局部存储
    """

    TRACE_HEADER = "HTTP_X_TRACE_ID"
    RESPONSE_HEADER = "X-Trace-ID"

    def __init__(self, get_response: Callable[..., Any]) -> None:
        """初始化中间件

        Args:
            get_response: Django 提供的下一层处理函数
        """
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        """处理请求，注入 trace_id

        Args:
            request: Django HttpRequest

        Returns:
            Django HttpResponse
        """
        # 1. 优先从 OpenTelemetry Span Context 获取（与 Jaeger 一致）
        trace_id = get_otel_trace_id()

        # 2. 回退到 X-Trace-ID header
        if not trace_id:
            trace_id = request.META.get(self.TRACE_HEADER) or generate_trace_id()

        # 3. 存储到 request 与线程局部存储
        set_trace_id(request, trace_id)

        try:
            # 4. 调用下一层
            response = self.get_response(request)

            # 5. 在响应头中设置 trace_id
            response[self.RESPONSE_HEADER] = trace_id
            return response
        finally:
            # 6. 清理线程局部存储，避免线程池复用串号
            clear_trace_id()
            clear_duration()
