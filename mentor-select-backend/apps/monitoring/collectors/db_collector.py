"""DB SQL 采集器

用于统计单个 Request 周期内的 SQL 查询数量、慢查询次数与总耗时。

工作原理：
- DEBUG=True 时，Django 会将所有 SQL 查询记录到 connection.queries
  本采集器在请求开始时记录 queries 长度，结束时计算增量
- DEBUG=False 时，connection.queries 为空，返回零值统计

慢查询阈值：500ms（0.5s）
"""
from __future__ import annotations

from typing import Any

from django.db import connection

# 慢查询阈值（秒）
SLOW_QUERY_THRESHOLD: float = 0.5


class DBCollector:
    """SQL 查询统计采集器

    使用方式：
        collector = DBCollector()
        collector.start_tracking()
        # ... 业务代码 ...
        stats = collector.stop_tracking()
        # stats = {"sql_count": 10, "slow_query_count": 1, "total_sql_time": 0.234}
    """

    def __init__(self) -> None:
        """初始化采集器"""
        self._initial_query_count: int = 0
        self._tracking: bool = False

    def start_tracking(self) -> None:
        """开始追踪 SQL 查询

        记录当前 connection.queries 的长度作为基线。
        """
        try:
            self._initial_query_count = len(connection.queries_log())
        except Exception:
            # DEBUG=False 或其他异常情况下，queries 为空
            self._initial_query_count = 0
        self._tracking = True

    def stop_tracking(self) -> dict[str, int | float | dict[str, int]]:
        """停止追踪并返回统计结果

        Returns:
            包含以下字段的字典：
            - sql_count: SQL 查询次数
            - slow_query_count: 慢查询次数（耗时 > SLOW_QUERY_THRESHOLD）
            - total_sql_time: SQL 总耗时（秒）
            - method_counts: 按 SQL 方法分类的查询次数，如 {"SELECT": 8, "INSERT": 2}

            若 DEBUG=False，所有字段均为 0。
        """
        if not self._tracking:
            return {
                "sql_count": 0,
                "slow_query_count": 0,
                "total_sql_time": 0.0,
                "method_counts": {},
            }

        self._tracking = False

        try:
            queries = list(connection.queries_log())
        except Exception:
            return {
                "sql_count": 0,
                "slow_query_count": 0,
                "total_sql_time": 0.0,
                "method_counts": {},
            }

        # 仅统计 start_tracking 之后的查询
        new_queries = queries[self._initial_query_count:]

        sql_count = len(new_queries)
        slow_query_count = 0
        total_sql_time = 0.0
        method_counts: dict[str, int] = {}

        for query in new_queries:
            # query 格式：{"sql": "...", "time": "0.001"}（time 单位：秒，字符串）
            try:
                elapsed = float(query.get("time", 0))
            except (TypeError, ValueError):
                elapsed = 0.0
            total_sql_time += elapsed
            if elapsed > SLOW_QUERY_THRESHOLD:
                slow_query_count += 1

            # 解析 SQL 方法（首词大写）
            sql_text = query.get("sql", "").strip().upper()
            if sql_text:
                method = sql_text.split()[0].split("(")[0]
                if method in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    method_counts[method] = method_counts.get(method, 0) + 1
                else:
                    method_counts["OTHER"] = method_counts.get("OTHER", 0) + 1

        return {
            "sql_count": sql_count,
            "slow_query_count": slow_query_count,
            "total_sql_time": total_sql_time,
            "method_counts": method_counts,
        }

    @staticmethod
    def is_available() -> bool:
        """检查 SQL 追踪是否可用

        DEBUG=True 时 Django 才会记录 SQL 查询。

        Returns:
            True 表示可用
        """
        try:
            from django.conf import settings

            return bool(settings.DEBUG)
        except Exception:
            return False

    @staticmethod
    def get_slow_query_threshold() -> float:
        """获取慢查询阈值（秒）

        Returns:
            慢查询阈值
        """
        return SLOW_QUERY_THRESHOLD
