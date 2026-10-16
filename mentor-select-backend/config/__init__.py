"""
项目初始化文件
导入 Celery app
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
