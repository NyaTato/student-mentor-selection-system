"""
自定义异常和全局异常处理器

异常体系：
- BusinessException: 业务异常基类，携带业务错误码
- ValidationError: 参数校验异常
- AuthenticationFailedError: 认证异常
- PermissionDeniedError: 权限异常
- NotFoundError: 资源不存在
- ConflictError: 并发冲突
- StateTransitionError: 状态机异常

全局异常处理器 custom_exception_handler：
- 将所有异常统一转换为 ApiResponse 格式
- 处理 DRF APIException / Django Http404 / PermissionDenied / ValidationError
- 捕获未预期异常并记录日志，返回 500
"""
import logging

from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.common.error_codes import ErrorCode, get_http_status

logger = logging.getLogger("apps.common.exceptions")


class BusinessException(APIException):
    """业务异常基类

    使用方式：
        raise BusinessException("名额已满", code=ErrorCode.QUOTA_EXCEEDED)
        raise BusinessException(code=ErrorCode.STATE_NOT_ALLOWED, message="状态不允许")
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "业务处理失败"
    default_code = ErrorCode.BUSINESS_ERROR

    def __init__(self, message=None, code=None):
        # message 走 detail，code 走业务错误码
        if code is not None:
            self.default_code = code
            # 根据 code 自动选择 HTTP 状态码
            self.status_code = get_http_status(code)
        if message is not None:
            self.default_detail = message
        super().__init__(detail=self.default_detail, code=self.default_code)


class ValidationError(APIException):
    """参数校验异常"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "参数校验失败"
    default_code = ErrorCode.PARAM_INVALID


class AuthenticationFailedError(APIException):
    """认证异常"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "认证失败"
    default_code = ErrorCode.AUTH_FAILED


class PermissionDeniedError(APIException):
    """权限异常"""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "无权限"
    default_code = ErrorCode.PERMISSION_DENIED


class NotFoundError(APIException):
    """资源不存在"""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "资源不存在"
    default_code = ErrorCode.NOT_FOUND


class ConflictError(APIException):
    """并发冲突"""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "资源冲突"
    default_code = ErrorCode.CONFLICT


class StateTransitionError(BusinessException):
    """状态机转换异常

    用于系统状态推进/回退不合法的情况。
    """

    default_code = ErrorCode.SYSTEM_STATE_INVALID_TRANSITION
    default_detail = "状态转换不合法"

    def __init__(self, message=None, code=None):
        if code is None:
            code = ErrorCode.SYSTEM_STATE_INVALID_TRANSITION
        if message is None:
            message = "状态转换不合法"
        super().__init__(message=message, code=code)


def _normalize_detail(exc) -> str:
    """从异常对象中提取可读的错误信息"""
    detail = getattr(exc, "detail", None)
    if detail is None:
        return str(exc) or "未知错误"

    # DRF 的 detail 可能是字符串、列表、字典
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        # 取第一个错误信息
        return detail[0] if detail else "参数校验失败"
    if isinstance(detail, dict):
        # 取第一个字段的第一个错误
        for key, value in detail.items():
            if isinstance(value, list):
                return f"{key}: {value[0]}" if value else f"{key}: 校验失败"
            return f"{key}: {value}"
        return "参数校验失败"
    return str(detail)


def _resolve_error_code(exc) -> int:
    """从异常对象中解析业务错误码"""
    # DRF APIException 的 code 可能是字符串（如 'invalid'）或整数
    raw_code = getattr(exc, "default_code", None)
    if isinstance(raw_code, int):
        return raw_code

    # 通过类型推断错误码
    if isinstance(exc, AuthenticationFailedError):
        return ErrorCode.AUTH_FAILED
    if isinstance(exc, PermissionDeniedError):
        return ErrorCode.PERMISSION_DENIED
    if isinstance(exc, NotFoundError):
        return ErrorCode.NOT_FOUND
    if isinstance(exc, ConflictError):
        return ErrorCode.CONFLICT
    if isinstance(exc, ValidationError):
        return ErrorCode.PARAM_INVALID
    if isinstance(exc, BusinessException):
        return ErrorCode.BUSINESS_ERROR

    # DRF 内置异常
    from rest_framework.exceptions import (
        AuthenticationFailed,
        NotAuthenticated,
        PermissionDenied,
    )

    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return ErrorCode.AUTH_FAILED
    if isinstance(exc, PermissionDenied):
        return ErrorCode.PERMISSION_DENIED

    return ErrorCode.BUSINESS_ERROR


def custom_exception_handler(exc, context):
    """全局异常处理器

    将所有异常统一包装为 ApiResponse 格式：
    {code: <业务错误码>, message: <错误信息>, data: None}

    处理顺序：
    1. 调用 DRF 默认 handler 处理已知 APIException
    2. 处理 Django ValidationError / Http404 / PermissionDenied
    3. 捕获未预期异常，记录 ERROR 日志，返回 500
    """
    # DRF 已知异常
    response = exception_handler(exc, context)

    if response is not None:
        error_code = _resolve_error_code(exc)
        message = _normalize_detail(exc)
        response.data = {
            "code": error_code,
            "message": message,
            "data": None,
        }
        return response

    # Django ValidationError（非 DRF）
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            message = "; ".join(
                f"{k}: {', '.join(v)}" for k, v in exc.message_dict.items()
            )
        elif hasattr(exc, "messages"):
            message = "; ".join(exc.messages)
        else:
            message = "参数校验失败"
        logger.warning("Django ValidationError: %s", message)
        return Response(
            {"code": ErrorCode.PARAM_INVALID, "message": message, "data": None},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Django Http404
    if isinstance(exc, Http404):
        message = str(exc) if str(exc) != "Not Found" else "资源不存在"
        return Response(
            {"code": ErrorCode.NOT_FOUND, "message": message, "data": None},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Django PermissionDenied
    if isinstance(exc, DjangoPermissionDenied):
        message = str(exc) or "无权限"
        return Response(
            {"code": ErrorCode.PERMISSION_DENIED, "message": message, "data": None},
            status=status.HTTP_403_FORBIDDEN,
        )

    # 未预期异常：记录完整堆栈，返回 500
    logger.exception("Unhandled exception: %s", exc)
    return Response(
        {
            "code": ErrorCode.SYSTEM_ERROR,
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
