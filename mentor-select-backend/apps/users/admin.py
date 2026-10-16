"""
用户管理 Admin 注册
"""
from django.contrib import admin

from apps.users.models import AdminProfile, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """用户管理"""

    list_display = (
        "id",
        "username",
        "role",
        "status",
        "is_staff",
        "is_superuser",
        "created_at",
    )
    list_filter = ("role", "status", "is_staff", "is_superuser")
    search_fields = ("username",)
    list_editable = ("role", "status")
    ordering = ("-id",)
    fieldsets = (
        ("基本信息", {"fields": ("username", "password")}),
        ("角色与状态", {"fields": ("role", "status")}),
        ("权限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("重要日期", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    readonly_fields = ("last_login", "date_joined", "created_at", "updated_at")


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    """管理员档案管理"""

    list_display = ("user", "name", "created_at", "updated_at")
    search_fields = ("name", "user__username")
    ordering = ("-user_id",)
    readonly_fields = ("created_at", "updated_at")
