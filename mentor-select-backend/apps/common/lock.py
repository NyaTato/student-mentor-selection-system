"""分布式锁 + 幂等 Token 基础设施

依据 DATABASE.md 8.1 / 8.3：
- 分布式锁：SET NX EX，超时自动释放
- 幂等 Token：SET NX EX，用过即删

锁使用场景：
- lock:application:{year}:{student}:{round} — 防并发重复申请（10 sec）
- lock:admission:{year}:{teacher} — 防并发超额录取（30 sec）
- lock:state:transition:{year} — 防并发状态切换（10 sec）
- lock:state:auto_transition:{year} — 防自动与手动切换并发（30 sec）
- lock:academic_year:activate — 防并发学年激活（30 sec）
- lock:auto_assign:{year} — 防并发自动分配（300 sec）

一致性保障（DATABASE.md 8.5）：
- 录取校验必须查 DB + 行锁，不能依赖缓存
- 缓存 miss 或不一致时，以 DB 为准
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Generator

from apps.common.cache_keys import TTL_IDEMPOTENT, idempotent
from apps.common.logger import get_logger
from apps.common.redis_client import get_redis_client

logger = get_logger("common.lock")


class LockAcquisitionError(Exception):
    """分布式锁获取失败"""


class DistributedLock:
    """分布式锁

    基于 Redis SET NX EX 实现：
    - 获取锁：SET key value NX EX ttl
    - 释放锁：Lua 脚本校验 value 后 DEL（防止误删他人持有的锁）

    使用方式（上下文管理器）：
        with DistributedLock("lock:auto_assign:1", ttl=300) as acquired:
            if not acquired:
                raise LockAcquisitionError("自动分配任务正在执行")
            # 执行业务逻辑

    使用方式（手动）：
        lock = DistributedLock("lock:state:transition:1", ttl=10)
        if lock.acquire():
            try:
                # 业务逻辑
            finally:
                lock.release()
        else:
            raise LockAcquisitionError("状态切换正在进行")
    """

    # Lua 脚本：校验 value 后 DEL，防止误删
    _RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, key: str, ttl: int = 10, token: str | None = None):
        """
        Args:
            key: Redis Key
            ttl: 锁超时时间（秒），超时自动释放
            token: 锁持有标识，默认自动生成 UUID
        """
        self.key = key
        self.ttl = ttl
        self.token = token or str(uuid.uuid4())
        self._acquired = False

    def acquire(self, blocking: bool = False, blocking_timeout: float = 0) -> bool:
        """获取锁

        Args:
            blocking: 是否阻塞等待
            blocking_timeout: 阻塞超时时间（秒）

        Returns:
            True 表示获取成功
        """
        import time

        client = get_redis_client()
        start_time = time.time()

        while True:
            result = client.set(self.key, self.token, nx=True, ex=self.ttl)
            if result:
                self._acquired = True
                logger.debug("Lock acquired: key=%s, token=%s", self.key, self.token)
                return True

            if not blocking:
                logger.debug("Lock acquire failed (non-blocking): key=%s", self.key)
                return False

            if blocking_timeout > 0 and (time.time() - start_time) >= blocking_timeout:
                logger.debug("Lock acquire timeout: key=%s", self.key)
                return False

            time.sleep(0.1)

    def release(self) -> bool:
        """释放锁

        使用 Lua 脚本校验 token 后删除，防止误删他人持有的锁。

        Returns:
            True 表示释放成功
        """
        if not self._acquired:
            return False

        client = get_redis_client()
        result = client.eval(self._RELEASE_SCRIPT, 1, self.key, self.token)
        self._acquired = False

        if result:
            logger.debug("Lock released: key=%s, token=%s", self.key, self.token)
            return True
        else:
            logger.warning(
                "Lock release failed (already expired or held by others): key=%s",
                self.key,
            )
            return False

    def __enter__(self) -> bool:
        """进入上下文，返回是否获取成功"""
        return self.acquire()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出上下文，自动释放锁"""
        if self._acquired:
            self.release()

    @property
    def is_acquired(self) -> bool:
        """是否已获取锁"""
        return self._acquired


@contextmanager
def acquire_lock(
    key: str, ttl: int = 10, raise_on_fail: bool = True
) -> Generator[DistributedLock, None, None]:
    """获取分布式锁的便捷上下文管理器

    Args:
        key: Redis Key
        ttl: 锁超时时间（秒）
        raise_on_fail: 获取失败时是否抛异常

    Yields:
        DistributedLock 实例

    Raises:
        LockAcquisitionError: 获取失败且 raise_on_fail=True
    """
    lock = DistributedLock(key, ttl=ttl)
    acquired = lock.acquire()
    try:
        if not acquired and raise_on_fail:
            raise LockAcquisitionError(f"无法获取锁: {key}")
        yield lock
    finally:
        if acquired:
            lock.release()


class IdempotentToken:
    """幂等 Token

    依据 DATABASE.md 8.1：
    - Key: idempotent:{request_id}
    - TTL: 5 min
    - 策略：SET NX EX，用过即删

    使用方式：
        token = IdempotentToken("req-abc-123")
        if token.acquire():
            try:
                # 处理请求
                result = do_business()
                token.store_result(result)
                return result
            finally:
                token.release()
        else:
            # 重复请求，返回上次结果
            return token.get_stored_result()
    """

    def __init__(self, request_id: str, ttl: int = TTL_IDEMPOTENT):
        """
        Args:
            request_id: 请求唯一标识
            ttl: Token 有效期（秒），默认 5 min
        """
        self.request_id = request_id
        self.ttl = ttl
        self.key = idempotent(request_id)
        self._acquired = False

    def acquire(self) -> bool:
        """获取幂等 Token（SET NX EX）

        Returns:
            True 表示首次请求，可继续处理
            False 表示重复请求
        """
        client = get_redis_client()
        result = client.set(self.key, "1", nx=True, ex=self.ttl)
        if result:
            self._acquired = True
            logger.debug("Idempotent token acquired: request_id=%s", self.request_id)
            return True
        logger.debug("Idempotent token duplicate: request_id=%s", self.request_id)
        return False

    def store_result(self, result: Any) -> None:
        """存储处理结果（用于重复请求时返回）

        Args:
            result: 可序列化的处理结果（dict / str / int 等）
        """
        import json

        client = get_redis_client()
        client.set(self.key, json.dumps(result, ensure_ascii=False, default=str), ex=self.ttl)

    def get_stored_result(self) -> Any | None:
        """获取已存储的处理结果

        Returns:
            上次处理结果，无则返回 None
        """
        import json

        client = get_redis_client()
        value = client.get(self.key)
        if value is None or value == "1":
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def release(self) -> None:
        """释放 Token（删除 Key）"""
        if self._acquired:
            client = get_redis_client()
            client.delete(self.key)
            self._acquired = False
            logger.debug("Idempotent token released: request_id=%s", self.request_id)


def check_idempotent(request_id: str) -> bool:
    """检查幂等 Token 是否可用（快捷方法）

    Returns:
        True 表示首次请求，False 表示重复请求
    """
    token = IdempotentToken(request_id)
    return token.acquire()
