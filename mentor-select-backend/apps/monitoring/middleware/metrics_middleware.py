"""Metrics 中间件

采集 HTTP 请求层的核心 metrics：
- 请求耗时（Histogram）
- 请求总数（Counter）
- 并发请求数（Gauge）
- 请求 / 响应体大小（Summary）
- SQL 查询次数 / 耗时 / 慢查询（DEBUG=True 时）

设计要点：
- 跳过 /metrics、/admin、/static、/media 等非业务路径
- path 规范化：将 /api/v1/students/123/ 转为 /api/v1/students/{id}/，
  避免 label 基数爆炸
- 异常安全：metrics 记录失败不能影响请求处理
- SQL 统计仅在 DEBUG=True 时有效（Django 限制），生产环境依赖 MySQL slow_query_log
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable

from apps.monitoring.collectors.db_collector import DBCollector
from apps.monitoring.metrics.registry import (
    API_CONCURRENT_REQUESTS,
    API_REQUEST_DURATION,
    API_REQUESTS_TOTAL,
    API_REQUEST_SIZE_BYTES,
    API_RESPONSE_SIZE_BYTES,
    SQL_DURATION,
    SQL_QUERIES_TOTAL,
    SQL_SLOW_QUERIES_TOTAL,
)
from apps.monitoring.utils.trace import set_duration

# 跳过 metrics 采集的路径前缀
SKIP_PATH_PREFIXES: tuple[str, ...] = (
    "/metrics",
    "/admin",
    "/static",
    "/media",
    "/api/schema",
    "/api/docs",
)

# 匹配路径中的数字 ID，如 /api/v1/students/123/ → /api/v1/students/{id}/
# 支持：整数、UUID（含横线）
_PATH_ID_PATTERN = re.compile(r"/(?P<id_part>(?:\d+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}))(?:/|$)")


def normalize_path(path: str) -> str:
    """规范化路径，将 ID 替换为 {id}

    避免高基数 label 导致 Prometheus 内存爆炸。

    Args:
        path: 原始路径，如 /api/v1/students/123/

    Returns:
        规范化路径，如 /api/v1/students/{id}/
    """
    return _PATH_ID_PATTERN.sub("/{id}/", path)


def should_skip(path: str) -> bool:
    """判断是否跳过该路径的 metrics 采集

    Args:
        path: 请求路径

    Returns:
        True 表示跳过
    """
    return any(path.startswith(prefix) for prefix in SKIP_PATH_PREFIXES)


class MetricsMiddleware:
    """HTTP 请求 metrics 采集中间件"""

    def __init__(self, get_response: Callable[..., Any]) -> None:
        """初始化中间件

        Args:
            get_response: Django 提供的下一层处理函数
        """
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        """处理请求并采集 metrics

        Args:
            request: Django HttpRequest

        Returns:
            Django HttpResponse
        """
        path = request.path

        # 跳过非业务路径
        if should_skip(path):
            return self.get_response(request)

        # 规范化路径，避免 ID 导致 label 基数爆炸
        normalized_path = normalize_path(path)
        method = request.method or "UNKNOWN"

        # 记录请求体大小（content-length 头）
        try:
            content_length = int(request.META.get("CONTENT_LENGTH", 0) or 0)
        except (TypeError, ValueError):
            content_length = 0

        # 记录开始时间，递增并发数
        start_time = time.perf_counter()
        API_CONCURRENT_REQUESTS.inc()

        # SQL 查询追踪（仅 DEBUG=True 时有效）
        db_collector = DBCollector()
        db_collector.start_tracking()

        try:
            response = self.get_response(request)
        finally:
            # 无论是否异常，都要递减并发数并记录耗时
            API_CONCURRENT_REQUESTS.dec()

        # 计算耗时（秒）
        duration = time.perf_counter() - start_time

        # 将请求耗时写入线程局部存储，供后续日志的 duration 字段引用
        set_duration(duration)

        # 获取状态码（异常时为 500）
        status = getattr(response, "status_code", 500)

        # 安全地记录 metrics，任一记录失败都不影响响应返回
        try:
            API_REQUEST_DURATION.labels(
                method=method,
                path=normalized_path,
                status=str(status),
            ).observe(duration)
        except Exception:
            pass

        try:
            API_REQUESTS_TOTAL.labels(
                method=method,
                path=normalized_path,
                status=str(status),
            ).inc()
        except Exception:
            pass

        try:
            API_REQUEST_SIZE_BYTES.labels(
                method=method,
                path=normalized_path,
            ).observe(content_length)
        except Exception:
            pass

        try:
            # 响应体大小：优先从 Content-Length 头获取
            response_size = 0
            if hasattr(response, "headers"):
                response_size = int(response.headers.get("Content-Length", 0) or 0)
            elif hasattr(response, "get"):
                # HttpResponse 兼容
                cl = response.get("Content-Length")
                if cl:
                    try:
                        response_size = int(cl)
                    except (TypeError, ValueError):
                        response_size = 0
            # 如果无法从头获取，尝试从 content 长度推断
            if response_size == 0 and hasattr(response, "content"):
                response_size = len(response.content or b"")
            API_RESPONSE_SIZE_BYTES.labels(
                method=method,
                path=normalized_path,
            ).observe(response_size)
        except Exception:
            pass

        # SQL 查询统计（DEBUG=True 时有效，生产环境返回零值）
        try:
            sql_stats = db_collector.stop_tracking()
            sql_count = sql_stats.get("sql_count", 0)
            slow_count = sql_stats.get("slow_query_count", 0)
            sql_time = sql_stats.get("total_sql_time", 0.0)
            method_counts = sql_stats.get("method_counts", {})

            if sql_count > 0:
                # 按 SQL 方法分类记录查询次数
                for sql_method, count in method_counts.items():
                    SQL_QUERIES_TOTAL.labels(method=sql_method).inc(count)
                SQL_DURATION.observe(sql_time)

            if slow_count > 0:
                SQL_SLOW_QUERIES_TOTAL.inc(slow_count)
        except Exception:
            pass

        return response
