"""RabbitMQ 消息队列基础设施

依据 DATABASE.md 第九部分 RabbitMQ 设计：
- 8 个队列：app.notify / log.operation / log.login / assign.auto / assign.revoke / assign.result / import.excel / import.result
- 通用消息信封：{id, type, ts, data}
- 失败重试：3 次，5s/30s/120s 指数退避
- 死信队列：{queue}.dlq

同步 vs 异步边界（DATABASE.md 9.1）：
- 同步：导师录取、状态切换、状态回退、学年激活、管理员人工分配
- 异步：自动分配、撤销自动分配、Excel 导入、操作日志、登录日志、通知
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pika
from django.conf import settings

from apps.common.logger import get_logger
from apps.monitoring.services import MetricsService

logger = get_logger("common.mq")


# ===== 消息类型枚举 =====


class MessageType(str, Enum):
    """消息类型（对应 DATABASE.md 9.2 的 8 个队列）"""

    APP_NOTIFY = "app.notify"
    LOG_OPERATION = "log.operation"
    LOG_LOGIN = "log.login"
    ASSIGN_AUTO = "assign.auto"
    ASSIGN_REVOKE = "assign.revoke"
    ASSIGN_RESULT = "assign.result"
    IMPORT_EXCEL = "import.excel"
    IMPORT_RESULT = "import.result"


# ===== 队列配置 =====


@dataclass
class QueueConfig:
    """队列配置"""

    name: str
    routing_key: str
    durable: bool = True
    # 死信队列配置
    dlq_name: str = ""
    # 重试配置（DATABASE.md 9.5：3 次重试，5s/30s/120s 指数退避）
    max_retries: int = 3
    retry_delays: list[int] = field(default_factory=lambda: [5, 30, 120])

    def __post_init__(self):
        if not self.dlq_name:
            self.dlq_name = f"{self.name}.dlq"


# 8 个队列配置（DATABASE.md 9.2）
QUEUE_CONFIGS: dict[MessageType, QueueConfig] = {
    MessageType.APP_NOTIFY: QueueConfig(
        name="app.notify",
        routing_key="app.notify",
    ),
    MessageType.LOG_OPERATION: QueueConfig(
        name="log.operation",
        routing_key="log.operation",
        # 日志类重试耗尽后丢弃，不影响主流程（DATABASE.md 9.5）
    ),
    MessageType.LOG_LOGIN: QueueConfig(
        name="log.login",
        routing_key="log.login",
    ),
    MessageType.ASSIGN_AUTO: QueueConfig(
        name="assign.auto",
        routing_key="assign.auto",
    ),
    MessageType.ASSIGN_REVOKE: QueueConfig(
        name="assign.revoke",
        routing_key="assign.revoke",
    ),
    MessageType.ASSIGN_RESULT: QueueConfig(
        name="assign.result",
        routing_key="assign.result",
    ),
    MessageType.IMPORT_EXCEL: QueueConfig(
        name="import.excel",
        routing_key="import.excel",
    ),
    MessageType.IMPORT_RESULT: QueueConfig(
        name="import.result",
        routing_key="import.result",
    ),
}

# 日志类队列（重试耗尽后丢弃）
LOG_QUEUE_TYPES = {MessageType.LOG_OPERATION, MessageType.LOG_LOGIN}


# ===== 消息信封 =====


@dataclass
class Message:
    """通用消息信封（DATABASE.md 9.3）

    {
        "id": "uuid-v4",
        "type": "app.notify | log.operation | ...",
        "ts": "2026-07-07T12:00:00.000000Z",
        "data": { ... }
    }
    """

    type: MessageType
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # 重试次数（0 表示首次发送）
    retry_count: int = 0

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps(
            {
                "id": self.id,
                "type": self.type.value,
                "ts": self.ts,
                "data": self.data,
                "retry_count": self.retry_count,
            },
            ensure_ascii=False,
            default=str,
        )

    @classmethod
    def from_json(cls, body: str | bytes) -> "Message":
        """从 JSON 反序列化"""
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        obj = json.loads(body)
        return cls(
            type=MessageType(obj["type"]),
            data=obj["data"],
            id=obj["id"],
            ts=obj["ts"],
            retry_count=obj.get("retry_count", 0),
        )

    def get_retry_delay(self) -> int | None:
        """获取下次重试延迟（秒）

        依据 DATABASE.md 9.5：3 次重试，5s/30s/120s 指数退避
        """
        config = QUEUE_CONFIGS[self.type]
        if self.retry_count >= config.max_retries:
            return None  # 重试耗尽
        if self.retry_count < len(config.retry_delays):
            return config.retry_delays[self.retry_count]
        return config.retry_delays[-1]  # 使用最后一个延迟

    def should_dead_letter(self) -> bool:
        """是否应该进入死信队列

        依据 DATABASE.md 9.5：
        - 日志类：重试耗尽后丢弃
        - 业务类：重试耗尽后进死信
        """
        if self.type in LOG_QUEUE_TYPES:
            return False  # 日志类丢弃，不进死信
        config = QUEUE_CONFIGS[self.type]
        return self.retry_count >= config.max_retries


# ===== RabbitMQ 连接 =====


def get_connection() -> pika.BlockingConnection:
    """获取 RabbitMQ 连接

    使用 settings 中的 CELERY_BROKER_URL 或 RABBITMQ_* 配置。
    """
    broker_url = getattr(settings, "CELERY_BROKER_URL", "")

    if broker_url and broker_url.startswith("amqp://"):
        params = pika.URLParameters(broker_url)
    else:
        params = pika.ConnectionParameters(
            host=getattr(settings, "RABBITMQ_HOST", "127.0.0.1"),
            port=int(getattr(settings, "RABBITMQ_PORT", 5672)),
            credentials=pika.PlainCredentials(
                username=getattr(settings, "RABBITMQ_USER", "guest"),
                password=getattr(settings, "RABBITMQ_PASSWORD", "guest"),
            ),
            virtual_host=getattr(settings, "RABBITMQ_VHOST", "/"),
            heartbeat=600,
            blocked_connection_timeout=300,
        )

    return pika.BlockingConnection(params)


# ===== 队列声明 =====


def declare_queues(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """声明所有队列 + 死信队列

    为每个队列创建：
    1. 死信队列（{queue}.dlq）— durable
    2. 主队列 — durable，配置 x-dead-letter-exchange 指向死信交换机

    依据 DATABASE.md 9.5：死信队列 {queue}.dlq
    """
    for msg_type, config in QUEUE_CONFIGS.items():
        # 声明死信队列
        channel.queue_declare(queue=config.dlq_name, durable=config.durable)
        # 声明主队列，配置死信路由
        channel.queue_declare(
            queue=config.name,
            durable=config.durable,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": config.dlq_name,
            },
        )
        logger.debug("Queue declared: %s (DLQ: %s)", config.name, config.dlq_name)


# ===== Producer =====


class MessageProducer:
    """消息生产者

    使用方式：
        producer = MessageProducer()
        producer.publish(Message(
            type=MessageType.LOG_LOGIN,
            data={"user_id": 1, "username": "admin", "ok": True},
        ))

    连接管理：每次 publish 创建新连接，避免长连接断开问题。
    生产环境可使用连接池优化。
    """

    def publish(self, message: Message) -> bool:
        """发布消息到队列

        Args:
            message: 消息信封

        Returns:
            True 表示发布成功
        """
        try:
            connection = get_connection()
            channel = connection.channel()
            declare_queues(channel)

            config = QUEUE_CONFIGS[message.type]
            channel.basic_publish(
                exchange="",
                routing_key=config.routing_key,
                body=message.to_json().encode("utf-8"),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 持久化
                    content_type="application/json",
                    message_id=message.id,
                    timestamp=int(datetime.now(timezone.utc).timestamp()),
                ),
            )
            connection.close()

            logger.info(
                "Message published: type=%s, id=%s, retry=%d",
                message.type.value, message.id, message.retry_count,
            )
            MetricsService.record_mq_publish(queue=message.type.value)
            return True

        except Exception as exc:
            logger.error(
                "Message publish failed: type=%s, error=%s",
                message.type.value, exc,
            )
            return False

    def publish_retry(self, message: Message) -> bool:
        """发布重试消息（延迟重试）

        依据 DATABASE.md 9.5：重试间隔 5s/30s/120s 指数退避

        实现方式：使用 TTL 队列 + 死信转发实现延迟重试
        - 创建临时重试队列，设置 TTL
        - 消息过期后通过死信转发回主队列

        Args:
            message: 需要重试的消息（retry_count 已递增）

        Returns:
            True 表示重试消息发布成功
        """
        delay = message.get_retry_delay()
        if delay is None:
            # 重试耗尽，进入死信队列或丢弃
            if message.should_dead_letter():
                return self._publish_to_dlq(message)
            else:
                logger.warning(
                    "Message dropped (max retries): type=%s, id=%s",
                    message.type.value, message.id,
                )
                return True

        try:
            connection = get_connection()
            channel = connection.channel()

            config = QUEUE_CONFIGS[message.type]
            retry_queue = f"{config.name}.retry.{delay}"

            # 声明重试队列（TTL + 死信转发回主队列）
            channel.queue_declare(
                queue=retry_queue,
                durable=True,
                arguments={
                    "x-message-ttl": delay * 1000,  # 毫秒
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": config.routing_key,
                },
            )

            channel.basic_publish(
                exchange="",
                routing_key=retry_queue,
                body=message.to_json().encode("utf-8"),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                    message_id=message.id,
                ),
            )
            connection.close()

            logger.info(
                "Retry message published: type=%s, id=%s, retry=%d, delay=%ds",
                message.type.value, message.id, message.retry_count, delay,
            )
            MetricsService.record_mq_retry(queue=message.type.value)
            return True

        except Exception as exc:
            logger.error(
                "Retry publish failed: type=%s, error=%s",
                message.type.value, exc,
            )
            return False

    def _publish_to_dlq(self, message: Message) -> bool:
        """发布到死信队列"""
        try:
            connection = get_connection()
            channel = connection.channel()

            config = QUEUE_CONFIGS[message.type]
            channel.basic_publish(
                exchange="",
                routing_key=config.dlq_name,
                body=message.to_json().encode("utf-8"),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                    message_id=message.id,
                ),
            )
            connection.close()

            logger.warning(
                "Message dead-lettered: type=%s, id=%s, retries=%d",
                message.type.value, message.id, message.retry_count,
            )
            MetricsService.record_mq_dead_letter(queue=message.type.value)
            return True

        except Exception as exc:
            logger.error(
                "DLQ publish failed: type=%s, error=%s",
                message.type.value, exc,
            )
            return False


# ===== 便捷发布函数 =====


def publish_log_login(
    user_id: int,
    username: str,
    ip: str,
    ua: str,
    ok: bool,
    reason: str | None = None,
) -> bool:
    """发布登录日志消息（DATABASE.md 9.3 log.login）

    Args:
        user_id: 用户 ID
        username: 用户名
        ip: 客户端 IP
        ua: User-Agent
        ok: 是否登录成功
        reason: 失败原因（登录失败时填写）
    """
    producer = MessageProducer()
    return producer.publish(
        Message(
            type=MessageType.LOG_LOGIN,
            data={
                "user_id": user_id,
                "username": username,
                "ip": ip,
                "ua": ua,
                "ok": ok,
                "reason": reason,
            },
        )
    )


def publish_log_operation(
    academic_year_id: int,
    user_id: int,
    action: int,
    target_type: str,
    target_id: int,
    detail: str = "{}",
    ip: str = "",
) -> bool:
    """发布操作日志消息（DATABASE.md 9.3 log.operation）"""
    producer = MessageProducer()
    return producer.publish(
        Message(
            type=MessageType.LOG_OPERATION,
            data={
                "academic_year_id": academic_year_id,
                "user_id": user_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "detail": detail,
                "ip": ip,
            },
        )
    )


def publish_app_notify(
    academic_year_id: int,
    student_id: int,
    teacher_id: int,
    action: str,
    round_num: int,
) -> bool:
    """发布申请状态变更通知（DATABASE.md 9.3 app.notify）"""
    producer = MessageProducer()
    return producer.publish(
        Message(
            type=MessageType.APP_NOTIFY,
            data={
                "academic_year_id": academic_year_id,
                "student_id": student_id,
                "teacher_id": teacher_id,
                "action": action,
                "round": round_num,
            },
        )
    )


def publish_assign_auto(
    academic_year_id: int,
    triggered_by: int,
    unassigned_count: int,
) -> bool:
    """发布自动分配消息（DATABASE.md 9.3 assign.auto）"""
    producer = MessageProducer()
    return producer.publish(
        Message(
            type=MessageType.ASSIGN_AUTO,
            data={
                "academic_year_id": academic_year_id,
                "triggered_by": triggered_by,
                "unassigned_count": unassigned_count,
            },
        )
    )


def publish_assign_revoke(
    academic_year_id: int,
    auto_assignment_log_id: int,
    revoked_by: int,
) -> bool:
    """发布撤销自动分配消息（DATABASE.md 9.3 assign.revoke）"""
    producer = MessageProducer()
    return producer.publish(
        Message(
            type=MessageType.ASSIGN_REVOKE,
            data={
                "academic_year_id": academic_year_id,
                "auto_assignment_log_id": auto_assignment_log_id,
                "revoked_by": revoked_by,
            },
        )
    )


def publish_import_excel(
    task_id: int,
    academic_year_id: int,
    role: int,
    file_path: str,
) -> bool:
    """发布 Excel 导入消息（DATABASE.md 9.3 import.excel）"""
    producer = MessageProducer()
    return producer.publish(
        Message(
            type=MessageType.IMPORT_EXCEL,
            data={
                "task_id": task_id,
                "academic_year_id": academic_year_id,
                "role": role,
                "file_path": file_path,
            },
        )
    )
