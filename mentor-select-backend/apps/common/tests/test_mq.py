"""RabbitMQ 消息队列测试

使用 unittest.mock 模拟 pika 连接，避免依赖真实 RabbitMQ 服务。
测试覆盖：
- Message: 序列化/反序列化/重试延迟/死信判断
- QueueConfig: 队列配置
- MessageProducer: publish/publish_retry/DLQ
- 便捷发布函数
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.common.mq import (
    LOG_QUEUE_TYPES,
    QUEUE_CONFIGS,
    Message,
    MessageProducer,
    MessageType,
    QueueConfig,
    publish_app_notify,
    publish_assign_auto,
    publish_assign_revoke,
    publish_import_excel,
    publish_log_login,
    publish_log_operation,
)


# ===== Message 测试 =====


class TestMessage:
    """消息信封测试"""

    def test_create_message(self):
        """创建消息"""
        msg = Message(
            type=MessageType.LOG_LOGIN,
            data={"user_id": 1, "username": "admin"},
        )
        assert msg.type == MessageType.LOG_LOGIN
        assert msg.data["user_id"] == 1
        assert msg.id is not None
        assert msg.ts is not None
        assert msg.retry_count == 0

    def test_to_json(self):
        """序列化为 JSON"""
        msg = Message(
            type=MessageType.APP_NOTIFY,
            data={"student_id": 100, "action": "accepted"},
        )
        json_str = msg.to_json()
        obj = json.loads(json_str)
        assert obj["type"] == "app.notify"
        assert obj["data"]["student_id"] == 100
        assert obj["id"] == msg.id

    def test_from_json(self):
        """从 JSON 反序列化"""
        original = Message(
            type=MessageType.ASSIGN_AUTO,
            data={"academic_year_id": 1, "triggered_by": 1},
            retry_count=2,
        )
        json_str = original.to_json()
        restored = Message.from_json(json_str)
        assert restored.type == MessageType.ASSIGN_AUTO
        assert restored.data["academic_year_id"] == 1
        assert restored.id == original.id
        assert restored.retry_count == 2

    def test_from_json_bytes(self):
        """从 bytes 反序列化"""
        msg = Message(type=MessageType.LOG_OPERATION, data={"action": 21})
        restored = Message.from_json(msg.to_json().encode("utf-8"))
        assert restored.type == MessageType.LOG_OPERATION

    def test_get_retry_delay_first(self):
        """首次重试延迟 5s"""
        msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=0)
        assert msg.get_retry_delay() == 5

    def test_get_retry_delay_second(self):
        """第二次重试延迟 30s"""
        msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=1)
        assert msg.get_retry_delay() == 30

    def test_get_retry_delay_third(self):
        """第三次重试延迟 120s"""
        msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=2)
        assert msg.get_retry_delay() == 120

    def test_get_retry_delay_exhausted(self):
        """重试耗尽返回 None"""
        msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=3)
        assert msg.get_retry_delay() is None

    def test_should_dead_letter_business(self):
        """业务类消息重试耗尽进死信"""
        msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=3)
        assert msg.should_dead_letter() is True

    def test_should_dead_letter_log(self):
        """日志类消息不进死信"""
        msg = Message(type=MessageType.LOG_OPERATION, data={}, retry_count=3)
        assert msg.should_dead_letter() is False

    def test_should_not_dead_letter(self):
        """未耗尽不进死信"""
        msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=2)
        assert msg.should_dead_letter() is False


# ===== QueueConfig 测试 =====


class TestQueueConfig:
    """队列配置测试"""

    def test_dlq_name_auto(self):
        """DLQ 名称自动生成"""
        config = QueueConfig(name="app.notify", routing_key="app.notify")
        assert config.dlq_name == "app.notify.dlq"

    def test_retry_config(self):
        """重试配置默认值"""
        config = QueueConfig(name="test", routing_key="test")
        assert config.max_retries == 3
        assert config.retry_delays == [5, 30, 120]

    def test_all_queues_configured(self):
        """所有 8 个队列已配置"""
        assert len(QUEUE_CONFIGS) == 8
        for msg_type in MessageType:
            assert msg_type in QUEUE_CONFIGS

    def test_queue_routing_key_matches_name(self):
        """路由 Key 与队列名一致"""
        for msg_type, config in QUEUE_CONFIGS.items():
            assert config.name == config.routing_key

    def test_log_queue_types(self):
        """日志队列类型"""
        assert MessageType.LOG_OPERATION in LOG_QUEUE_TYPES
        assert MessageType.LOG_LOGIN in LOG_QUEUE_TYPES
        assert MessageType.APP_NOTIFY not in LOG_QUEUE_TYPES


# ===== MessageProducer 测试 =====


class TestMessageProducer:
    """消息生产者测试"""

    def test_publish_success(self):
        """发布消息成功"""
        with patch("apps.common.mq.get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_channel = MagicMock()
            mock_conn.channel.return_value = mock_channel
            mock_get_conn.return_value = mock_conn

            producer = MessageProducer()
            msg = Message(type=MessageType.LOG_LOGIN, data={"user_id": 1})
            assert producer.publish(msg) is True

            mock_channel.basic_publish.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_publish_failure(self):
        """发布消息失败"""
        with patch("apps.common.mq.get_connection") as mock_get_conn:
            mock_get_conn.side_effect = Exception("连接失败")

            producer = MessageProducer()
            msg = Message(type=MessageType.LOG_LOGIN, data={"user_id": 1})
            assert producer.publish(msg) is False

    def test_publish_retry_with_delay(self):
        """重试消息发布（带延迟）"""
        with patch("apps.common.mq.get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_channel = MagicMock()
            mock_conn.channel.return_value = mock_channel
            mock_get_conn.return_value = mock_conn

            producer = MessageProducer()
            msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=0)
            assert producer.publish_retry(msg) is True

            # 验证发布到重试队列
            mock_channel.basic_publish.assert_called_once()
            args = mock_channel.basic_publish.call_args
            assert "retry" in args[1]["routing_key"]

    def test_publish_retry_exhausted_to_dlq(self):
        """重试耗尽进入死信队列"""
        with patch("apps.common.mq.get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_channel = MagicMock()
            mock_conn.channel.return_value = mock_channel
            mock_get_conn.return_value = mock_conn

            producer = MessageProducer()
            msg = Message(type=MessageType.APP_NOTIFY, data={}, retry_count=3)
            assert producer.publish_retry(msg) is True

            # 验证发布到 DLQ
            mock_channel.basic_publish.assert_called_once()
            args = mock_channel.basic_publish.call_args
            assert "dlq" in args[1]["routing_key"]

    def test_publish_retry_exhausted_log_dropped(self):
        """日志类重试耗尽丢弃"""
        with patch("apps.common.mq.get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_channel = MagicMock()
            mock_conn.channel.return_value = mock_channel
            mock_get_conn.return_value = mock_conn

            producer = MessageProducer()
            msg = Message(type=MessageType.LOG_OPERATION, data={}, retry_count=3)
            assert producer.publish_retry(msg) is True

            # 日志类不发布到任何队列，直接丢弃
            mock_channel.basic_publish.assert_not_called()


# ===== 便捷发布函数测试 =====


class TestPublishHelpers:
    """便捷发布函数测试"""

    def test_publish_log_login(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            result = publish_log_login(
                user_id=1,
                username="admin",
                ip="10.0.0.1",
                ua="Mozilla/5.0",
                ok=True,
            )
            assert result is True
            mock_publish.assert_called_once()
            msg = mock_publish.call_args[0][0]
            assert msg.type == MessageType.LOG_LOGIN
            assert msg.data["user_id"] == 1
            assert msg.data["ok"] is True

    def test_publish_log_login_failed(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            publish_log_login(
                user_id=0,
                username="wrong",
                ip="10.0.0.1",
                ua="Mozilla/5.0",
                ok=False,
                reason="密码错误",
            )
            msg = mock_publish.call_args[0][0]
            assert msg.data["ok"] is False
            assert msg.data["reason"] == "密码错误"

    def test_publish_log_operation(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            publish_log_operation(
                academic_year_id=1,
                user_id=1,
                action=21,
                target_type="application",
                target_id=12345,
            )
            msg = mock_publish.call_args[0][0]
            assert msg.type == MessageType.LOG_OPERATION
            assert msg.data["action"] == 21

    def test_publish_app_notify(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            publish_app_notify(
                academic_year_id=1,
                student_id=100,
                teacher_id=200,
                action="accepted",
                round_num=1,
            )
            msg = mock_publish.call_args[0][0]
            assert msg.type == MessageType.APP_NOTIFY
            assert msg.data["action"] == "accepted"

    def test_publish_assign_auto(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            publish_assign_auto(
                academic_year_id=1,
                triggered_by=1,
                unassigned_count=15,
            )
            msg = mock_publish.call_args[0][0]
            assert msg.type == MessageType.ASSIGN_AUTO
            assert msg.data["unassigned_count"] == 15

    def test_publish_assign_revoke(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            publish_assign_revoke(
                academic_year_id=1,
                auto_assignment_log_id=5,
                revoked_by=1,
            )
            msg = mock_publish.call_args[0][0]
            assert msg.type == MessageType.ASSIGN_REVOKE

    def test_publish_import_excel(self):
        with patch("apps.common.mq.MessageProducer.publish") as mock_publish:
            mock_publish.return_value = True
            publish_import_excel(
                task_id=10,
                academic_year_id=1,
                role=1,
                file_path="/tmp/upload/test.xlsx",
            )
            msg = mock_publish.call_args[0][0]
            assert msg.type == MessageType.IMPORT_EXCEL
            assert msg.data["task_id"] == 10
