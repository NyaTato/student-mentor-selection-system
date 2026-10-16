"""
日志工具

提供按模块/业务领域获取 logger 的便捷方法，以及审计日志、操作日志的辅助函数。

日志层级约定：
- DEBUG:   开发期 SQL / 内部状态
- INFO:    关键业务动作（登录、状态切换、申请提交）
- WARNING: 业务校验失败（参数错误、权限拒绝）
- ERROR:   系统异常、外部依赖失败
- CRITICAL: 数据损坏、服务不可用

使用方式：
    from apps.common.logger import get_logger
    logger = get_logger(__name__)
    logger.info("用户登录成功", extra={"user_id": user.id})
"""
import logging


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger

    所有业务 logger 应挂在 'apps' 命名空间下，便于统一配置。
    """
    if not name.startswith("apps.") and name != "apps":
        name = f"apps.{name}"
    return logging.getLogger(name)


def get_audit_logger() -> logging.Logger:
    """获取审计日志 logger

    审计日志记录关键业务操作（登录、状态切换、申请处理等），
    可单独配置 handler 写入独立文件或发送到日志中心。
    """
    return logging.getLogger("apps.audit")


def log_business_event(
    action: str,
    user_id: int | None = None,
    target: str | None = None,
    detail: str | None = None,
    level: str = "INFO",
):
    """记录业务事件

    Args:
        action: 操作动作（推荐使用 OperationAction 的 label）
        user_id: 操作者 ID
        target: 操作目标（如 "application:123"）
        detail: 附加说明
        level: 日志级别 INFO/WARNING/ERROR
    """
    logger = get_audit_logger()
    message_parts = [f"action={action}"]
    if user_id is not None:
        message_parts.append(f"user={user_id}")
    if target:
        message_parts.append(f"target={target}")
    if detail:
        message_parts.append(f"detail={detail}")
    message = " ".join(message_parts)

    extra = {
        "action": action,
        "user_id": user_id,
        "target": target,
        "detail": detail,
    }
    getattr(logger, level.lower(), logger.info)(message, extra=extra)


def log_login(user_id: int, username: str, success: bool, ip: str | None = None):
    """记录登录事件"""
    level = "INFO" if success else "WARNING"
    detail = f"ip={ip}" if ip else None
    log_business_event(
        action="LOGIN",
        user_id=user_id,
        target=f"user:{username}",
        detail=detail,
        level=level,
    )


def log_state_transition(
    user_id: int | None,
    academic_year_id: int,
    from_state: int,
    to_state: int,
    transition_type: str = "FORWARD",
):
    """记录状态切换"""
    log_business_event(
        action=f"STATE_{transition_type}",
        user_id=user_id,
        target=f"system_state:year={academic_year_id}",
        detail=f"{from_state}->{to_state}",
        level="INFO",
    )
