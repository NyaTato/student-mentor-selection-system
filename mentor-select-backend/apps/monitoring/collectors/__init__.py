"""采集器模块

导出 DB SQL 采集器。
"""
from apps.monitoring.collectors.db_collector import (
    DBCollector,
    SLOW_QUERY_THRESHOLD,
)

__all__ = [
    "DBCollector",
    "SLOW_QUERY_THRESHOLD",
]
