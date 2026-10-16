from django.contrib import admin

from apps.logs.models import LoginLog, OperationLog


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__"]
