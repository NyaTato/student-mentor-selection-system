"""smoke_view - 健康检查接口

检查服务存活状态、数据库连接、响应时间，不依赖 Redis/MQ。
"""
import time

from django.db import connections
from django.db.utils import OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def smoke(request):
    """健康检查

    GET /api/v2/smoke

    返回：
    - status: ok/degraded
    - checks.db: 数据库连接状态 (ok/fail)
    - checks.db_latency_ms: 数据库响应耗时（毫秒）
    - version: 后端版本
    """
    # 检测数据库连接
    db_status = "ok"
    db_latency_ms = 0
    try:
        start = time.time()
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_latency_ms = round((time.time() - start) * 1000, 2)
    except OperationalError:
        db_status = "fail"
    except Exception:
        db_status = "fail"

    overall = "ok" if db_status == "ok" else "degraded"

    return Response({
        "status": overall,
        "checks": {
            "db": db_status,
            "db_latency_ms": db_latency_ms,
        },
        "version": "v2",
    })
