"""生产启动密钥守卫测试（config.settings.key_guard）

最终评审要求：生产必须拒绝空/过短/默认/示例型 SECRET_KEY，
以及显式的弱 JWT_SIGNING_KEY；要求运维生成的随机密钥。

测试策略：直接调用纯校验函数（settings helper），
**不**以生产配置启动、**不**读取/打印任何本地 .env。
"""
from pathlib import Path

import pytest

from config.settings.key_guard import (
    MIN_JWT_SIGNING_KEY_LENGTH,
    MIN_SECRET_KEY_LENGTH,
    validate_jwt_signing_key,
    validate_production_keys,
    validate_secret_key,
)

# 由 secrets.token_urlsafe 生成的示例强密钥（仅测试用随机串）
STRONG_SECRET = "k7Qm2Zx9pL4vT8sR1nB6wY3cD5fH0jA2eG4uK9mP7tX1zV5bN8qW2rS6yU3iO0aE"
STRONG_JWT = "aB3cD5eF7gH9jK2lM4nP6qR8sT0uV1wX"


class TestSecretKeyGuard:
    """SECRET_KEY 强度规则"""

    @pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
    def test_missing_or_blank_rejected(self, value):
        with pytest.raises(RuntimeError):
            validate_secret_key(value)

    def test_short_key_rejected(self):
        """短于 50 字符一律拒绝"""
        short = "A" * (MIN_SECRET_KEY_LENGTH - 1)
        with pytest.raises(RuntimeError):
            validate_secret_key(short)

    def test_exactly_min_length_accepted(self):
        """恰好达到长度下限的随机串可通过"""
        value = "A" * MIN_SECRET_KEY_LENGTH
        validate_secret_key(value)  # 不抛异常

    def test_strong_random_key_accepted(self):
        assert len(STRONG_SECRET) >= MIN_SECRET_KEY_LENGTH
        validate_secret_key(STRONG_SECRET)

    @pytest.mark.parametrize(
        "value",
        [
            "django-insecure-change-me-in-production-please",
            "change-me-in-production-please-with-enough-length-0123456789",
            "this-is-an-example-secret-key-for-docs-0123456789abcdefghij",
            "your-secret-key-goes-here-0123456789abcdefghijklmnopqrstuv",
            "CHANGE_ME_PLEASE_WITH_ALSO_A_VERY_LONG_AND_USELESS_VALUE_1234",
            "default-secret-key-used-for-local-dev-0123456789abcdefghijk",
            "test-key-0123456789abcdefghijklmnopqrstuvwxyz-0123456789",
            "placeholder-value-for-production-0123456789abcdefghijklmn",
        ],
    )
    def test_placeholder_values_rejected_even_when_long(self, value):
        """示例/占位符值即使足够长也必须拒绝（防止复制示例配置到生产）"""
        with pytest.raises(RuntimeError):
            validate_secret_key(value)

    def test_short_placeholder_also_rejected(self):
        with pytest.raises(RuntimeError):
            validate_secret_key("change-me")

    def test_default_django_key_rejected(self):
        """历史上只拦截这一个精确默认值，现在仍然被拦截"""
        with pytest.raises(RuntimeError):
            validate_secret_key("django-insecure-change-me-in-production-please")


class TestJwtSigningKeyGuard:
    """JWT_SIGNING_KEY 强度规则"""

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_absent_or_blank_falls_back_to_secret_key(self, value):
        """未设置 / 空白 → 回退到已校验的 SECRET_KEY，允许通过"""
        validate_jwt_signing_key(value)  # 不抛异常

    def test_strong_key_accepted(self):
        assert len(STRONG_JWT) >= MIN_JWT_SIGNING_KEY_LENGTH
        validate_jwt_signing_key(STRONG_JWT)

    def test_short_key_rejected(self):
        with pytest.raises(RuntimeError):
            validate_jwt_signing_key("A" * (MIN_JWT_SIGNING_KEY_LENGTH - 1))

    @pytest.mark.parametrize(
        "value",
        [
            "change-me-please-0123456789abcdefghijkl",
            "example-signing-key-0123456789abcdefghijklmnop",
            "this-is-a-placeholder-jwt-signing-key-0123456789",
        ],
    )
    def test_placeholder_key_rejected(self, value):
        with pytest.raises(RuntimeError):
            validate_jwt_signing_key(value)


class TestValidateProductionKeys:
    """组合入口（prod.py 调用的就是它）"""

    def test_valid_pair_accepted(self):
        validate_production_keys(STRONG_SECRET, STRONG_JWT)

    def test_secret_only_accepted_when_jwt_absent(self):
        validate_production_keys(STRONG_SECRET, None)

    def test_weak_secret_rejected_even_with_strong_jwt(self):
        with pytest.raises(RuntimeError):
            validate_production_keys("short-secret", STRONG_JWT)

    def test_strong_secret_with_weak_jwt_rejected(self):
        with pytest.raises(RuntimeError):
            validate_production_keys(STRONG_SECRET, "short")

    def test_strong_secret_with_placeholder_jwt_rejected(self):
        with pytest.raises(RuntimeError):
            validate_production_keys(STRONG_SECRET, "change-me-change-me-change-me-123456")


class TestProdSettingsWiring:
    """确认 prod.py 在启动时调用了守卫（静态检查，不真实启动生产配置）

    以生产 settings 真实导入需要真实的运维密钥环境，本仓库禁止读取/改动
    本地 .env，因此这里改为断言 prod.py 确实接入了守卫与回退逻辑。
    """

    def test_prod_settings_calls_guard(self):
        from django.conf import settings as django_settings

        prod_path = (
            Path(django_settings.BASE_DIR) / "config" / "settings" / "prod.py"
        )
        source = prod_path.read_text(encoding="utf-8")
        assert "validate_production_keys(" in source
        # 同时确认 JWT 签名密钥有「显式值 / 回退 SECRET_KEY」两条路径
        assert 'SIMPLE_JWT["SIGNING_KEY"]' in source

    def test_dev_test_settings_untouched_by_guard(self):
        """dev/test 配置不调用生产守卫（本地与测试环境不被阻塞）"""
        from django.conf import settings as django_settings

        settings_dir = Path(django_settings.BASE_DIR) / "config" / "settings"
        for name in ("base.py", "test.py", "dev.py"):
            source = (settings_dir / name).read_text(encoding="utf-8")
            assert "validate_production_keys(" not in source
