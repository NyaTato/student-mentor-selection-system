"""Model app 配置

将 model/ 注册为 Django app，使 Django Model 生效。
app_label = 'model'，与现有 apps/ 下的 app 隔离。
"""
from django.apps import AppConfig


class ModelConfig(AppConfig):
    """Model app 配置"""

    name = 'model'
    label = 'model'
    default_auto_field = 'django.db.models.BigAutoField'
