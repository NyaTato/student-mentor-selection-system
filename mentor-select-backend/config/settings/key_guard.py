"""生产环境密钥强度校验（纯函数，便于单测，不读取任何环境文件）

背景（review-checkpoints.md 最终评审要求）
----------------------------------------
生产配置原先只拒绝「精确等于 django 默认值」的 SECRET_KEY：把示例配置
（空值 / change-me / example / 过短）复制到生产后，JWT 可被任意伪造。

本模块提供与 Django settings 解耦的纯校验函数，由 ``config.settings.prod``
在启动时调用；测试直接调用函数即可覆盖全部规则，**无需**以生产配置启动、
也不读取/打印运维本地的 ``.env``。

规则
----
* ``SECRET_KEY``：必须由运维显式生成随机值，长度 >= 50，且不含占位符标记。
* ``JWT_SIGNING_KEY``：未设置 / 空白 → 回退到已通过校验的 ``SECRET_KEY``（允许）；
  显式设置时必须长度 >= 32 且不含占位符标记（否则拒绝，防止弱签名密钥）。
"""
from __future__ import annotations

MIN_SECRET_KEY_LENGTH = 50
MIN_JWT_SIGNING_KEY_LENGTH = 32

# 占位符 / 示例值标记（大小写不敏感的子串匹配）
_PLACEHOLDER_MARKERS = (
    "change-me",
    "change_me",
    "changeme",
    "insecure",
    "placeholder",
    "example",
    "your-secret",
    "your_secret",
    "secret-key",
    "secret_key",
    "default",
    "password",
    "django-default",
    "sample-key",
    "test-key",
    "testkey",
    "todo",
    "fixme",
    "xxxx",
)


def _is_placeholder(value: str) -> bool:
    """值是否包含明显的占位符标记"""
    lowered = value.strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def validate_secret_key(secret_key: str | None) -> None:
    """校验生产 SECRET_KEY 强度，不合规抛出 RuntimeError

    Raises:
        RuntimeError: 未设置 / 空白 / 过短 / 命中占位符标记
    """
    if secret_key is None or not secret_key.strip():
        raise RuntimeError(
            "生产环境必须显式设置 SECRET_KEY 环境变量（不能为空）。"
            "请用随机方式生成至少 50 个字符的密钥，例如："
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    if _is_placeholder(secret_key):
        raise RuntimeError(
            "生产环境 SECRET_KEY 命中占位符/示例值标记（如 change-me、example、"
            "insecure、default 等）。请改用随机生成的运维专属密钥。"
        )

    if len(secret_key.strip()) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"生产环境 SECRET_KEY 长度不足（当前 {len(secret_key.strip())}，"
            f"要求 >= {MIN_SECRET_KEY_LENGTH}）。请用随机方式生成密钥，例如："
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )


def validate_jwt_signing_key(jwt_signing_key: str | None) -> None:
    """校验生产 JWT_SIGNING_KEY 强度

    未设置 / 空白视为「回退到已校验的 SECRET_KEY」，允许通过。

    Raises:
        RuntimeError: 显式设置但过短或命中占位符标记
    """
    if jwt_signing_key is None or not jwt_signing_key.strip():
        return

    if _is_placeholder(jwt_signing_key):
        raise RuntimeError(
            "生产环境 JWT_SIGNING_KEY 命中占位符/示例值标记，"
            "请改用随机生成的密钥，或留空以回退到 SECRET_KEY。"
        )

    if len(jwt_signing_key.strip()) < MIN_JWT_SIGNING_KEY_LENGTH:
        raise RuntimeError(
            f"生产环境 JWT_SIGNING_KEY 长度不足（当前 "
            f"{len(jwt_signing_key.strip())}，要求 >= {MIN_JWT_SIGNING_KEY_LENGTH}），"
            "请改用随机生成的密钥，或留空以回退到 SECRET_KEY。"
        )


def validate_production_keys(
    secret_key: str | None, jwt_signing_key: str | None = None
) -> None:
    """生产启动密钥总校验入口（由 config.settings.prod 调用）"""
    validate_secret_key(secret_key)
    validate_jwt_signing_key(jwt_signing_key)
