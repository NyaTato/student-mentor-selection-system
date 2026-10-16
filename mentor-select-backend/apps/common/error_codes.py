"""
统一错误码定义

依据 Backend-Architecture-Final-Report.md 异常体系规划：
- 0       成功
- 1xxxx   通用错误（认证/权限/参数/系统）
- 2xxxx   用户模块
- 3xxxx   学生模块
- 4xxxx   导师模块
- 5xxxx   申请模块
- 6xxxx   分配模块
- 7xxxx   公告模块
- 8xxxx   学年模块
- 9xxxx   系统状态模块
- 10xxxx  导入模块
- 11xxxx  日志模块
"""


class ErrorCode:
    """错误码常量

    使用常量而非 Enum，便于在 APIException 中作为字符串/整数 code 传递，
    同时避免与 DRF default_code 字符串冲突。
    """

    # ===== 通用错误 =====
    SUCCESS = 0
    UNKNOWN_ERROR = 10000
    SYSTEM_ERROR = 10001
    SERVICE_UNAVAILABLE = 10002

    # 认证 11xxx
    AUTH_FAILED = 11001
    TOKEN_INVALID = 11002
    TOKEN_EXPIRED = 11003
    LOGIN_REQUIRED = 11004
    ACCOUNT_DISABLED = 11005

    # 权限 12xxx
    PERMISSION_DENIED = 12001
    ROLE_MISMATCH = 12002

    # 参数 13xxx
    PARAM_INVALID = 13001
    PARAM_MISSING = 13002
    PARAM_TYPE_ERROR = 13003

    # 资源 14xxx
    NOT_FOUND = 14001
    CONFLICT = 14002
    DUPLICATE = 14003
    VERSION_CONFLICT = 14004

    # 限流 15xxx
    RATE_LIMITED = 15001

    # 业务通用 19xxx
    BUSINESS_ERROR = 19000
    STATE_NOT_ALLOWED = 19001
    QUOTA_EXCEEDED = 19002

    # ===== 用户模块 2xxxx =====
    USER_NOT_FOUND = 20001
    USER_EXISTS = 20002
    USER_PROFILE_NOT_FOUND = 20003
    PASSWORD_INCORRECT = 20004
    PASSWORD_WEAK = 20005

    # ===== 学生模块 3xxxx =====
    STUDENT_NOT_FOUND = 30001
    STUDENT_NUMBER_EXISTS = 30002

    # ===== 导师模块 4xxxx =====
    TEACHER_NOT_FOUND = 40001
    TEACHER_NUMBER_EXISTS = 40002
    QUOTA_NOT_FOUND = 40003
    QUOTA_INVALID = 40004

    # ===== 申请模块 5xxxx =====
    APPLICATION_NOT_FOUND = 50001
    APPLICATION_DUPLICATE = 50002
    APPLICATION_ROUND_CLOSED = 50003
    APPLICATION_LIMIT_EXCEEDED = 50004
    APPLICATION_STATUS_INVALID = 50005
    APPLICATION_ALREADY_PROCESSED = 50006

    # ===== 分配模块 6xxxx =====
    ADMISSION_NOT_FOUND = 60001
    ADMISSION_EXISTS = 60002
    ADMISSION_QUOTA_FULL = 60003
    AUTO_ASSIGN_RUNNING = 60004
    AUTO_ASSIGN_PREVIEW_FAILED = 60005
    AUTO_ASSIGN_RUN_FAILED = 60006
    AUTO_ASSIGN_REVOKE_FAILED = 60007

    # ===== 公告模块 7xxxx =====
    ANNOUNCEMENT_NOT_FOUND = 70001

    # ===== 学年模块 8xxxx =====
    ACADEMIC_YEAR_NOT_FOUND = 80001
    ACADEMIC_YEAR_EXISTS = 80002
    ACADEMIC_YEAR_INACTIVE = 80003
    ACADEMIC_YEAR_ARCHIVED = 80004

    # ===== 系统状态模块 9xxxx =====
    SYSTEM_STATE_NOT_FOUND = 90001
    SYSTEM_STATE_INVALID_TRANSITION = 90002
    SYSTEM_STATE_ROLLBACK_FORBIDDEN = 90003
    SYSTEM_STATE_SCHEDULE_INVALID = 90004

    # ===== 导入模块 10xxxx =====
    IMPORT_TASK_NOT_FOUND = 100001
    IMPORT_FILE_INVALID = 100002
    IMPORT_ROW_FAILED = 100003

    # ===== 日志模块 11xxxx =====
    LOG_NOT_FOUND = 110001


# HTTP 状态码映射
# 业务错误码 -> 合适的 HTTP 状态码
HTTP_STATUS_MAP = {
    ErrorCode.SUCCESS: 200,
    ErrorCode.UNKNOWN_ERROR: 500,
    ErrorCode.SYSTEM_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.AUTH_FAILED: 401,
    ErrorCode.TOKEN_INVALID: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.LOGIN_REQUIRED: 401,
    ErrorCode.ACCOUNT_DISABLED: 401,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.ROLE_MISMATCH: 403,
    ErrorCode.PARAM_INVALID: 400,
    ErrorCode.PARAM_MISSING: 400,
    ErrorCode.PARAM_TYPE_ERROR: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.DUPLICATE: 409,
    ErrorCode.VERSION_CONFLICT: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.BUSINESS_ERROR: 400,
    ErrorCode.STATE_NOT_ALLOWED: 400,
    ErrorCode.QUOTA_EXCEEDED: 400,
}


def get_http_status(error_code: int) -> int:
    """根据业务错误码获取 HTTP 状态码

    默认返回 400（业务错误），未匹配的 5xx 系统错误返回 500。
    """
    return HTTP_STATUS_MAP.get(error_code, 400)
