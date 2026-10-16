"""统一错误码常量（v2 API）

设计说明：
- v2 API 错误码统一在此定义，禁止在 View 中硬编码数字（Magic Number）
- 与 apps/common/error_codes.py（v1）保持独立，避免 v1/v2 schema 耦合
- 错误码范围 1001-1999，避免与 v1 的 10000+ 冲突

错误码区间：
- 1001-1099 通用错误（参数/校验/业务/系统）
- 1101-1199 用户模块
- 1201-1299 学生模块
- 1301-1399 导师模块
- 1401-1499 管理员模块
"""


class ErrorCode:
    """v2 API 错误码常量"""

    # ===== 通用错误 =====
    SUCCESS = 0
    VALIDATION_ERROR = 1001     # 参数校验失败
    LOGIN_FAILED = 1002         # 用户名或密码错误
    NOT_FOUND = 1003            # 资源不存在
    BUSINESS_ERROR = 1004       # 业务错误（ValueError 等）
    PASSWORD_INCORRECT = 1005   # 旧密码错误
    SYSTEM_ERROR = 10001        # 服务器内部错误（与 v1 SYSTEM_ERROR 一致）
