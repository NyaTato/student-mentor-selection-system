"""Prometheus Metrics 定义注册表

所有 metrics 统一前缀 `mentor_match_`，遵循 DESIGN.md 6.5 命名规范：
- Counter：以 `_total` 结尾（总量）
- Histogram：以 `_duration` 结尾（耗时）/ `_bytes` 结尾（字节数）
- Gauge：瞬时值
- Summary：以 `_bytes` 结尾（字节数分布）
- 命名使用 snake_case

分类（DESIGN.md 6.3）：
- API Metrics：HTTP 请求层
- Business Metrics：登录、申请、审核、第二轮、分配、Excel 导入、状态切换、公告、学年
- Infrastructure Metrics：缓存、消息队列、Celery、SQL、Service/Repository 方法
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# ===== 标准 buckets =====
# 适用于耗时类 Histogram（单位：秒）
DURATION_BUCKETS: tuple[float, ...] = (
    0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0,
)

# 字节数 buckets（请求/响应体大小）
SIZE_BUCKETS: tuple[float, ...] = (
    100, 1000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000,
)


# =====================================================================
# API Metrics —— HTTP 请求层 (DESIGN.md 6.3: mentor_match_api_duration / _count / _concurrent_requests)
# =====================================================================

# 请求耗时直方图（labels: method, path, status）
API_REQUEST_DURATION = Histogram(
    name="mentor_match_api_duration",
    documentation="HTTP 请求处理耗时（秒）",
    labelnames=("method", "path", "status"),
    buckets=DURATION_BUCKETS,
)

# 请求总数计数器（labels: method, path, status）
# DESIGN.md 6.3: mentor_match_api_total（Counter 使用 _total 后缀）
API_REQUESTS_TOTAL = Counter(
    name="mentor_match_api_total",
    documentation="HTTP 请求总数",
    labelnames=("method", "path", "status"),
)

# 当前并发请求数（瞬时值）
# DESIGN.md 6.3: mentor_match_concurrent_requests（Gauge 无前缀）
API_CONCURRENT_REQUESTS = Gauge(
    name="mentor_match_concurrent_requests",
    documentation="当前正在处理的并发请求数",
)

# 请求体大小 Summary（labels: method, path）
API_REQUEST_SIZE_BYTES = Summary(
    name="mentor_match_api_request_size_bytes",
    documentation="HTTP 请求体大小（字节）",
    labelnames=("method", "path"),
)

# 响应体大小 Summary（labels: method, path）
API_RESPONSE_SIZE_BYTES = Summary(
    name="mentor_match_api_response_size_bytes",
    documentation="HTTP 响应体大小（字节）",
    labelnames=("method", "path"),
)


# =====================================================================
# Business Metrics —— 业务埋点 (DESIGN.md 6.3)
# =====================================================================

# ----- 登录 (mentor_match_login_duration) -----

# 登录次数（labels: status=success/fail）
LOGIN_TOTAL = Counter(
    name="mentor_match_login_total",
    documentation="用户登录次数",
    labelnames=("status",),
)

# 登录耗时
LOGIN_DURATION = Histogram(
    name="mentor_match_login_duration",
    documentation="用户登录处理耗时（秒）",
    buckets=DURATION_BUCKETS,
)

# ----- JWT -----

# JWT 刷新次数
JWT_REFRESH_TOTAL = Counter(
    name="mentor_match_jwt_refresh_total",
    documentation="JWT token 刷新次数",
)

# JWT 失效次数（过期 / 黑名单命中）
JWT_EXPIRY_TOTAL = Counter(
    name="mentor_match_jwt_expiry_total",
    documentation="JWT token 失效次数",
)

# ----- 学生申请 (mentor_match_apply_duration) -----

# 申请次数（labels: round=first/second, status=success/fail）
APPLICATION_TOTAL = Counter(
    name="mentor_match_application_total",
    documentation="学生申请次数",
    labelnames=("round", "status"),
)

# 第一轮申请耗时（labels: round）
APPLY_DURATION = Histogram(
    name="mentor_match_apply_duration",
    documentation="学生申请处理耗时（秒）",
    labelnames=("round",),
    buckets=DURATION_BUCKETS,
)

# 第二轮申请耗时（DESIGN.md 6.3 单独要求：mentor_match_second_round_duration）
SECOND_ROUND_DURATION = Histogram(
    name="mentor_match_second_round_duration",
    documentation="第二轮申请处理耗时（秒）",
    buckets=DURATION_BUCKETS,
)

# ----- 导师审核 (mentor_match_review_duration) -----

# 审核次数（labels: status=pass/reject）
REVIEW_TOTAL = Counter(
    name="mentor_match_review_total",
    documentation="导师审核次数",
    labelnames=("status",),
)

# 审核耗时
REVIEW_DURATION = Histogram(
    name="mentor_match_review_duration",
    documentation="导师审核处理耗时（秒）",
    buckets=DURATION_BUCKETS,
)

# ----- 自动分配 (mentor_match_assignment_duration) -----

# 分配次数（labels: status=success/fail）
ASSIGNMENT_TOTAL = Counter(
    name="mentor_match_assignment_total",
    documentation="分配执行次数",
    labelnames=("status",),
)

# 分配耗时
ASSIGNMENT_DURATION = Histogram(
    name="mentor_match_assignment_duration",
    documentation="分配处理耗时（秒）",
    buckets=DURATION_BUCKETS,
)

# 当前正在运行的自动分配数量（瞬时值）
ASSIGNMENT_RUNNING = Gauge(
    name="mentor_match_assignment_running",
    documentation="当前正在运行的自动分配任务数",
)

# 分配参与者数量（labels: type=students/teachers）
ASSIGNMENT_PARTICIPANTS = Gauge(
    name="mentor_match_assignment_participants",
    documentation="分配参与者数量",
    labelnames=("type",),
)

# ----- Excel 导入 (mentor_match_excel_duration) -----

# Excel 导入各阶段耗时（labels: stage=upload/parse/validate/write/total）
EXCEL_DURATION = Histogram(
    name="mentor_match_excel_duration",
    documentation="Excel 导入各阶段耗时（秒）",
    labelnames=("stage",),
    buckets=DURATION_BUCKETS,
)

# ----- 状态推进 (mentor_match_state_transition) -----

# 状态切换次数（labels: from_state, to_state）
STATE_TRANSITION_TOTAL = Counter(
    name="mentor_match_state_transition_total",
    documentation="系统状态切换次数",
    labelnames=("from_state", "to_state"),
)

# ----- 公告 (DESIGN.md 6.3: mentor_match_announcement) -----

# 公告操作次数（labels: action=create/update/delete/publish）
ANNOUNCEMENT_TOTAL = Counter(
    name="mentor_match_announcement_total",
    documentation="公告操作次数",
    labelnames=("action",),
)

# ----- 学年 (DESIGN.md 6.3: mentor_match_academic_year) -----

# 学年操作次数（labels: action=create/activate/close）
ACADEMIC_YEAR_TOTAL = Counter(
    name="mentor_match_academic_year_total",
    documentation="学年操作次数",
    labelnames=("action",),
)


# =====================================================================
# Infrastructure Metrics —— 基础设施
# =====================================================================

# ----- 缓存 -----

# 缓存操作次数（labels: operation=get/set/delete, result=hit/miss/success/fail）
CACHE_OPERATIONS_TOTAL = Counter(
    name="mentor_match_cache_operations_total",
    documentation="缓存操作次数",
    labelnames=("operation", "result"),
)

# 缓存操作耗时（labels: operation）
CACHE_DURATION = Histogram(
    name="mentor_match_cache_duration",
    documentation="缓存操作耗时（秒）",
    labelnames=("operation",),
    buckets=DURATION_BUCKETS,
)

# 缓存穿透次数
CACHE_PENETRATION_TOTAL = Counter(
    name="mentor_match_cache_penetration_total",
    documentation="缓存穿透次数（查询不存在的 key）",
)

# 缓存击穿次数
CACHE_BREAKDOWN_TOTAL = Counter(
    name="mentor_match_cache_breakdown_total",
    documentation="缓存击穿次数（热点 key 过期）",
)

# 缓存雪崩保护次数
CACHE_AVALANCHE_PROTECTION_TOTAL = Counter(
    name="mentor_match_cache_avalanche_protection_total",
    documentation="缓存雪崩保护触发次数",
)

# ----- 消息队列（RabbitMQ） -----

# 消息发布次数（labels: queue）
MQ_PUBLISH_TOTAL = Counter(
    name="mentor_match_mq_publish_total",
    documentation="消息发布次数",
    labelnames=("queue",),
)

# 消息消费次数（labels: queue）
MQ_CONSUME_TOTAL = Counter(
    name="mentor_match_mq_consume_total",
    documentation="消息消费次数",
    labelnames=("queue",),
)

# 消息重试次数（labels: queue）
MQ_RETRY_TOTAL = Counter(
    name="mentor_match_mq_retry_total",
    documentation="消息重试次数",
    labelnames=("queue",),
)

# 死信次数（labels: queue）
MQ_DEAD_LETTER_TOTAL = Counter(
    name="mentor_match_mq_dead_letter_total",
    documentation="死信次数",
    labelnames=("queue",),
)

# ACK 次数（labels: queue）
MQ_ACK_TOTAL = Counter(
    name="mentor_match_mq_ack_total",
    documentation="消息 ACK 次数",
    labelnames=("queue",),
)

# NACK 次数（labels: queue）
MQ_NACK_TOTAL = Counter(
    name="mentor_match_mq_nack_total",
    documentation="消息 NACK 次数",
    labelnames=("queue",),
)

# 消费耗时（labels: queue）
MQ_CONSUME_DURATION = Histogram(
    name="mentor_match_mq_consume_duration",
    documentation="消息消费处理耗时（秒）",
    labelnames=("queue",),
    buckets=DURATION_BUCKETS,
)

# ----- Celery 任务 -----

# Celery 任务次数（labels: task, status=success/fail）
# DESIGN.md 6.5: label 名使用 task（而非 task_name）
CELERY_TASK_TOTAL = Counter(
    name="mentor_match_celery_task_total",
    documentation="Celery 任务执行次数",
    labelnames=("task", "status"),
)

# Celery 任务耗时（labels: task）
CELERY_TASK_DURATION = Histogram(
    name="mentor_match_celery_task_duration",
    documentation="Celery 任务执行耗时（秒）",
    labelnames=("task",),
    buckets=DURATION_BUCKETS,
)

# ----- SQL (mentor_match_sql_duration) -----

# SQL 查询次数（labels: method=SELECT/INSERT/UPDATE/DELETE）
SQL_QUERIES_TOTAL = Counter(
    name="mentor_match_sql_queries_total",
    documentation="SQL 查询次数",
    labelnames=("method",),
)

# SQL 查询耗时
SQL_DURATION = Histogram(
    name="mentor_match_sql_duration",
    documentation="SQL 查询耗时（秒）",
    buckets=DURATION_BUCKETS,
)

# 慢查询次数（>500ms）
SQL_SLOW_QUERIES_TOTAL = Counter(
    name="mentor_match_sql_slow_queries_total",
    documentation="慢查询次数（耗时超过 500ms）",
)

# ----- Service / Repository 方法 (DESIGN.md 6.3) -----

# Service 方法耗时（labels: service, method）
SERVICE_DURATION = Histogram(
    name="mentor_match_service_duration",
    documentation="Service 方法执行耗时（秒）",
    labelnames=("service", "method"),
    buckets=DURATION_BUCKETS,
)

# Repository 方法耗时（labels: service, method）
# DESIGN.md 6.5: label 名使用 service（与 SERVICE_DURATION 一致，通过 metric name 区分）
REPOSITORY_DURATION = Histogram(
    name="mentor_match_repository_duration",
    documentation="Repository 方法执行耗时（秒）",
    labelnames=("service", "method"),
    buckets=DURATION_BUCKETS,
)
