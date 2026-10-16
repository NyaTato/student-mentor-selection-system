"""Repository 基类工具

提供 SQL 执行的通用工具，统一通过 Django connection 执行 raw SQL。
所有 Repository 共用此工具，避免重复代码。

职责：
- execute_query: 执行 SELECT，返回 list[dict]
- execute_one: 执行 SELECT，返回单个 dict 或 None
- execute_insert: 执行 INSERT，返回新记录 ID
- execute_update: 执行 UPDATE/DELETE，返回受影响行数
- execute_transaction: 事务辅助

禁止：业务逻辑
"""
from typing import Any, Optional

from django.db import connection, transaction


def execute_query(sql: str, params: Optional[list] = None) -> list[dict]:
    """执行查询 SQL，返回 list[dict]"""
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def execute_one(sql: str, params: Optional[list] = None) -> Optional[dict]:
    """执行查询 SQL，返回单个 dict 或 None"""
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))


def execute_insert(sql: str, params: Optional[list] = None) -> int:
    """执行 INSERT，返回新记录 ID（lastrowid）"""
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.lastrowid


def execute_update(sql: str, params: Optional[list] = None) -> int:
    """执行 UPDATE/DELETE，返回受影响行数"""
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.rowcount


def execute_transaction(callback) -> Any:
    """事务辅助：在事务中执行 callback，出错自动回滚"""
    with transaction.atomic():
        return callback()
