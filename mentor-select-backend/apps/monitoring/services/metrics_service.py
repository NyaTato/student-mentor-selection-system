"""Metrics 业务服务

提供业务特定的 metrics 记录方法，封装对底层 Prometheus metric 实例的访问。

设计原则：
- 所有方法都是 classmethod，无需实例化
- 所有方法都是异常安全的：metrics 记录失败不会抛出异常（通过 @_safe 装饰器）
- 业务代码只需调用本服务的方法，无需关心具体的 metric 实例

使用示例：
    MetricsService.record_login(success=True, duration=0.234)
    MetricsService.record_application(round_num=1, success=True, duration=0.05)
    MetricsService.record_cache_penetration()
"""
from __future__ import annotations

import logging
from typing import Any

from apps.monitoring.metrics.registry import (
    ACADEMIC_YEAR_TOTAL,
    ANNOUNCEMENT_TOTAL,
    APPLY_DURATION,
    APPLICATION_TOTAL,
    ASSIGNMENT_DURATION,
    ASSIGNMENT_PARTICIPANTS,
    ASSIGNMENT_RUNNING,
    ASSIGNMENT_TOTAL,
    CACHE_AVALANCHE_PROTECTION_TOTAL,
    CACHE_BREAKDOWN_TOTAL,
    CACHE_DURATION,
    CACHE_OPERATIONS_TOTAL,
    CACHE_PENETRATION_TOTAL,
    CELERY_TASK_DURATION,
    CELERY_TASK_TOTAL,
    EXCEL_DURATION,
    JWT_EXPIRY_TOTAL,
    JWT_REFRESH_TOTAL,
    LOGIN_DURATION,
    LOGIN_TOTAL,
    MQ_ACK_TOTAL,
    MQ_CONSUME_DURATION,
    MQ_CONSUME_TOTAL,
    MQ_DEAD_LETTER_TOTAL,
    MQ_NACK_TOTAL,
    MQ_PUBLISH_TOTAL,
    MQ_RETRY_TOTAL,
    REVIEW_DURATION,
    REVIEW_TOTAL,
    SECOND_ROUND_DURATION,
    SERVICE_DURATION,
    REPOSITORY_DURATION,
    SQL_DURATION,
    SQL_QUERIES_TOTAL,
    SQL_SLOW_QUERIES_TOTAL,
    STATE_TRANSITION_TOTAL,
)


logger = logging.getLogger(__name__)


def _safe(fn: Any) -> Any:
    """安全执行 decorator：吞掉所有异常，避免 metrics 失败影响业务

    异常会被记录到 debug 日志，便于排查 label 拼写错误等问题。
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.debug("metrics record failed", exc_info=True)

    return wrapper


class MetricsService:
    """业务 metrics 记录服务

    所有方法都是 classmethod，封装对 Prometheus metric 的访问。
    所有方法都是异常安全的：metrics 记录失败不会抛出异常。
    """

    # =================================================================
    # 登录 / 认证 (DESIGN.md 6.3: mentor_match_login_duration)
    # =================================================================

    @classmethod
    @_safe
    def record_login(cls, success: bool, duration: float) -> None:
        """记录登录事件

        Args:
            success: 是否登录成功
            duration: 登录耗时（秒）
        """
        status = "success" if success else "fail"
        LOGIN_TOTAL.labels(status=status).inc()
        LOGIN_DURATION.observe(duration)

    @classmethod
    @_safe
    def record_jwt_refresh(cls) -> None:
        """记录 JWT 刷新事件"""
        JWT_REFRESH_TOTAL.inc()

    @classmethod
    @_safe
    def record_jwt_expiry(cls) -> None:
        """记录 JWT 失效事件（过期 / 黑名单命中）"""
        JWT_EXPIRY_TOTAL.inc()

    # =================================================================
    # 学生申请 (DESIGN.md 6.3: mentor_match_apply_duration / mentor_match_second_round_duration)
    # =================================================================

    @classmethod
    @_safe
    def record_application(
        cls, round_num: int, success: bool, duration: float
    ) -> None:
        """记录学生申请事件

        Args:
            round_num: 申请轮次（1=第一轮, 2=第二轮）
            success: 是否申请成功
            duration: 申请耗时（秒）
        """
        round_label = "first" if round_num == 1 else "second"
        status = "success" if success else "fail"
        APPLICATION_TOTAL.labels(round=round_label, status=status).inc()
        APPLY_DURATION.labels(round=round_label).observe(duration)
        # 第二轮单独记录到 SECOND_ROUND_DURATION（DESIGN.md 6.3 要求）
        # 注意：这是设计要求的双 metric 记录，非重复计数。
        # APPLY_DURATION 用于第一轮 vs 第二轮对比分析，
        # SECOND_ROUND_DURATION 用于第二轮专项分析，Dashboard 查询时不应求和。
        if round_num == 2:
            SECOND_ROUND_DURATION.observe(duration)

    # =================================================================
    # 导师审核 (DESIGN.md 6.3: mentor_match_review_duration)
    # =================================================================

    @classmethod
    @_safe
    def record_review(cls, passed: bool, duration: float) -> None:
        """记录导师审核事件

        Args:
            passed: 是否通过
            duration: 审核耗时（秒）
        """
        status = "pass" if passed else "reject"
        REVIEW_TOTAL.labels(status=status).inc()
        REVIEW_DURATION.observe(duration)

    # =================================================================
    # 自动分配 (DESIGN.md 6.3: mentor_match_assignment_duration)
    # =================================================================

    @classmethod
    @_safe
    def record_assignment(cls, success: bool, duration: float) -> None:
        """记录分配事件

        Args:
            success: 是否分配成功
            duration: 分配耗时（秒）
        """
        status = "success" if success else "fail"
        ASSIGNMENT_TOTAL.labels(status=status).inc()
        ASSIGNMENT_DURATION.observe(duration)

    @classmethod
    @_safe
    def record_assignment_start(cls, participants: dict[str, int]) -> None:
        """记录分配开始

        递增运行中的分配数，并记录参与者数量。

        Args:
            participants: 参与者字典，如 {"students": 100, "teachers": 20}
        """
        ASSIGNMENT_RUNNING.inc()
        if "students" in participants:
            ASSIGNMENT_PARTICIPANTS.labels(type="students").set(
                participants["students"]
            )
        if "teachers" in participants:
            ASSIGNMENT_PARTICIPANTS.labels(type="teachers").set(
                participants["teachers"]
            )

    @classmethod
    @_safe
    def record_assignment_end(cls) -> None:
        """记录分配结束

        递减运行中的分配数。
        """
        ASSIGNMENT_RUNNING.dec()

    # =================================================================
    # Excel 导入 (DESIGN.md 6.3: mentor_match_excel_duration)
    # =================================================================

    @classmethod
    @_safe
    def record_excel_import(cls, stage: str, duration: float) -> None:
        """记录 Excel 导入阶段耗时

        Args:
            stage: 阶段名称，可选值：
                - upload: 上传
                - parse: 解析
                - validate: 校验
                - write: 写入数据库
                - total: 整体
            duration: 该阶段耗时（秒）
        """
        EXCEL_DURATION.labels(stage=stage).observe(duration)

    # =================================================================
    # 状态机 (DESIGN.md 6.3: mentor_match_state_transition)
    # =================================================================

    @classmethod
    @_safe
    def record_state_transition(cls, from_state: int, to_state: int) -> None:
        """记录系统状态切换

        Args:
            from_state: 原状态码
            to_state: 目标状态码
        """
        STATE_TRANSITION_TOTAL.labels(
            from_state=str(from_state),
            to_state=str(to_state),
        ).inc()

    # =================================================================
    # 公告 (DESIGN.md 6.3: mentor_match_announcement)
    # =================================================================

    @classmethod
    @_safe
    def record_announcement(cls, action: str) -> None:
        """记录公告操作

        Args:
            action: 操作类型，可选值：
                - create: 创建
                - update: 更新
                - delete: 删除
                - publish: 发布
        """
        ANNOUNCEMENT_TOTAL.labels(action=action).inc()

    # =================================================================
    # 学年 (DESIGN.md 6.3: mentor_match_academic_year)
    # =================================================================

    @classmethod
    @_safe
    def record_academic_year(cls, action: str) -> None:
        """记录学年操作

        Args:
            action: 操作类型，可选值：
                - create: 创建
                - activate: 激活
                - close: 关闭
        """
        ACADEMIC_YEAR_TOTAL.labels(action=action).inc()

    # =================================================================
    # 缓存
    # =================================================================

    @classmethod
    @_safe
    def record_cache_operation(
        cls, operation: str, result: str, duration: float
    ) -> None:
        """记录缓存操作

        Args:
            operation: 操作类型，可选值：
                - get: 查询
                - set: 写入
                - delete: 删除
            result: 操作结果，可选值：
                - hit: 命中（仅 get）
                - miss: 未命中（仅 get）
                - success: 成功（set/delete）
                - fail: 失败
            duration: 操作耗时（秒）
        """
        CACHE_OPERATIONS_TOTAL.labels(operation=operation, result=result).inc()
        CACHE_DURATION.labels(operation=operation).observe(duration)

    @classmethod
    @_safe
    def record_cache_penetration(cls) -> None:
        """记录缓存穿透事件（查询不存在的 key）"""
        CACHE_PENETRATION_TOTAL.inc()

    @classmethod
    @_safe
    def record_cache_breakdown(cls) -> None:
        """记录缓存击穿事件（热点 key 过期）"""
        CACHE_BREAKDOWN_TOTAL.inc()

    @classmethod
    @_safe
    def record_cache_avalanche_protection(cls) -> None:
        """记录缓存雪崩保护触发事件"""
        CACHE_AVALANCHE_PROTECTION_TOTAL.inc()

    # =================================================================
    # 消息队列（RabbitMQ）
    # =================================================================

    @classmethod
    @_safe
    def record_mq_publish(cls, queue: str) -> None:
        """记录消息发布

        Args:
            queue: 队列名称
        """
        MQ_PUBLISH_TOTAL.labels(queue=queue).inc()

    @classmethod
    @_safe
    def record_mq_consume(
        cls, queue: str, duration: float, ack: bool = True
    ) -> None:
        """记录消息消费

        Args:
            queue: 队列名称
            duration: 消费耗时（秒）
            ack: 是否 ACK（True=ACK, False=NACK）
        """
        MQ_CONSUME_TOTAL.labels(queue=queue).inc()
        MQ_CONSUME_DURATION.labels(queue=queue).observe(duration)
        if ack:
            MQ_ACK_TOTAL.labels(queue=queue).inc()
        else:
            MQ_NACK_TOTAL.labels(queue=queue).inc()

    @classmethod
    @_safe
    def record_mq_retry(cls, queue: str) -> None:
        """记录消息重试

        Args:
            queue: 队列名称
        """
        MQ_RETRY_TOTAL.labels(queue=queue).inc()

    @classmethod
    @_safe
    def record_mq_dead_letter(cls, queue: str) -> None:
        """记录死信事件

        Args:
            queue: 队列名称
        """
        MQ_DEAD_LETTER_TOTAL.labels(queue=queue).inc()

    # =================================================================
    # Celery 任务
    # =================================================================

    @classmethod
    @_safe
    def record_celery_task(
        cls, task_name: str, success: bool, duration: float
    ) -> None:
        """记录 Celery 任务执行

        Args:
            task_name: 任务名称
            success: 是否成功
            duration: 执行耗时（秒）
        """
        status = "success" if success else "fail"
        CELERY_TASK_TOTAL.labels(task=task_name, status=status).inc()
        CELERY_TASK_DURATION.labels(task=task_name).observe(duration)

    # =================================================================
    # Service / Repository 方法 (DESIGN.md 6.3)
    # =================================================================

    @classmethod
    @_safe
    def record_service(cls, service: str, method: str, duration: float) -> None:
        """记录 Service 方法耗时

        Args:
            service: Service 类名
            method: 方法名
            duration: 执行耗时（秒）
        """
        SERVICE_DURATION.labels(service=service, method=method).observe(duration)

    @classmethod
    @_safe
    def record_repository(
        cls, repository: str, method: str, duration: float
    ) -> None:
        """记录 Repository 方法耗时

        Args:
            repository: Repository 类名
            method: 方法名
            duration: 执行耗时（秒）
        """
        REPOSITORY_DURATION.labels(
            service=repository, method=method
        ).observe(duration)

    # =================================================================
    # SQL 查询 (DESIGN.md 6.3: mentor_match_sql_duration)
    # =================================================================

    @classmethod
    @_safe
    def record_sql_query(cls, method: str, duration: float) -> None:
        """记录 SQL 查询

        Args:
            method: SQL 方法，可选值：
                - SELECT / INSERT / UPDATE / DELETE
            duration: 查询耗时（秒）
        """
        SQL_QUERIES_TOTAL.labels(method=method).inc()
        SQL_DURATION.observe(duration)

    @classmethod
    @_safe
    def record_slow_query(cls) -> None:
        """记录慢查询事件（耗时 > 500ms）"""
        SQL_SLOW_QUERIES_TOTAL.inc()
