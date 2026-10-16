"""
认证路由
JWT 登录、刷新、退出、获取当前用户、修改密码
"""
from django.urls import path

from .views import (
    ChangePasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RefreshTokenView,
)

urlpatterns = [
    # 登录
    path("login/", LoginView.as_view(), name="auth-login"),
    # 退出
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    # 刷新 Token
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    # 当前用户信息
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    # 修改密码
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
]
