"""
工具函数
"""
import uuid

from django.utils import timezone


def generate_uuid():
    """生成 UUID"""
    return str(uuid.uuid4())


def now():
    """获取当前时间"""
    return timezone.now()


def get_client_ip(request):
    """获取客户端 IP"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")
