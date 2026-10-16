"""User API 接口测试

fixtures（api_client / jwt_client 等）由 api/tests/conftest.py 自动发现，
不再使用 `from api.tests.conftest import *`：import-star 会把 conftest 中的同名人
（含根 conftest fixtures）注入测试模块作用域，造成静默覆盖。
"""
import pytest

from apps.users.models import User


@pytest.mark.django_db
def test_user_login_param_validation(api_client):
    """登录参数校验：缺少 password 应返回 400"""
    response = api_client.post("/api/v2/users/login", {"username": "testuser"}, format="json")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] != 0
    assert "message" in data


@pytest.mark.django_db
def test_user_login_wrong_credentials(api_client):
    """登录失败：不存在的用户返回 401"""
    response = api_client.post(
        "/api/v2/users/login",
        {"username": "nonexistent", "password": "WrongPass123"},
        format="json",
    )
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == 1002


@pytest.mark.django_db
def test_create_user_param_validation_short_password(api_client):
    """创建用户参数校验：密码少于 8 位应返回 400"""
    response = api_client.post(
        "/api/v2/users/create",
        {"username": "newuser", "password": "short", "role": 1},
        format="json",
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == 1001


@pytest.mark.django_db
def test_create_user_param_validation_invalid_role(api_client):
    """创建用户参数校验：无效角色应返回 400"""
    response = api_client.post(
        "/api/v2/users/create",
        {"username": "newuser", "password": "ValidPass123", "role": 99},
        format="json",
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == 1001


@pytest.mark.django_db
def test_create_user_success(api_client):
    """创建用户成功"""
    response = api_client.post(
        "/api/v2/users/create",
        {"username": "newuser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert "user_id" in data["data"]


@pytest.mark.django_db
def test_create_user_duplicate(api_client):
    """创建重复用户应失败"""
    payload = {"username": "dupuser", "password": "ValidPass123", "role": 1}
    # 第一次创建
    api_client.post("/api/v2/users/create", payload, format="json")
    # 第二次创建应失败
    response = api_client.post("/api/v2/users/create", payload, format="json")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == 1004


@pytest.mark.django_db
def test_user_login_after_create(api_client):
    """创建用户后可以登录"""
    api_client.post(
        "/api/v2/users/create",
        {"username": "loginuser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    response = api_client.post(
        "/api/v2/users/login",
        {"username": "loginuser", "password": "ValidPass123"},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "登录成功"
    assert data["data"]["username"] == "loginuser"
    # 密码不应返回
    assert "password" not in data["data"]


@pytest.mark.django_db
def test_get_user_not_found(api_client):
    """获取不存在的用户返回 404"""
    response = api_client.get("/api/v2/users/99999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == 1003


@pytest.mark.django_db
def test_list_users(api_client):
    """查询用户列表"""
    # 创建几个用户
    for i in range(3):
        api_client.post(
            "/api/v2/users/create",
            {"username": f"listuser{i}", "password": "ValidPass123", "role": 1},
            format="json",
        )
    response = api_client.get("/api/v2/users/list?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "list" in data["data"]
    assert "total" in data["data"]
    assert data["data"]["total"] >= 3


@pytest.mark.django_db
def test_list_users_param_validation(api_client):
    """查询用户列表参数校验：page_size 超过 100 应返回 400"""
    response = api_client.get("/api/v2/users/list?page=1&page_size=200")
    assert response.status_code == 400


@pytest.mark.django_db
def test_disable_enable_user(api_client):
    """禁用/启用用户"""
    # 创建用户
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "disableuser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    # 禁用
    response = api_client.put(f"/api/v2/users/{user_id}/disable")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 验证已禁用（登录应失败）
    login_resp = api_client.post(
        "/api/v2/users/login",
        {"username": "disableuser", "password": "ValidPass123"},
        format="json",
    )
    assert login_resp.status_code == 401
    # 启用
    response = api_client.put(f"/api/v2/users/{user_id}/enable")
    assert response.status_code == 200
    # 验证可以登录
    login_resp = api_client.post(
        "/api/v2/users/login",
        {"username": "disableuser", "password": "ValidPass123"},
        format="json",
    )
    assert login_resp.status_code == 200


@pytest.mark.django_db
def test_change_password(api_client, jwt_client):
    """修改密码：本人修改自己密码成功

    契约变更说明（2026-10-16 安全收紧）：
    change_password 从「任意已认证用户可改任意用户密码」收紧为「仅本人」。
    原测试用管理员客户端修改他人密码，因此改为以该用户本人的 v1 JWT 调用；
    断言内容（成功后新密码可登录、旧密码失败）保持不变。
    """
    # 创建用户
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "pwduser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    # 以本人 JWT 修改密码
    owner_client = jwt_client(User.objects.get(pk=user_id))
    response = owner_client.put(
        f"/api/v2/users/{user_id}/change_password",
        {"old_password": "ValidPass123", "new_password": "NewPass456"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 用新密码登录
    login_resp = api_client.post(
        "/api/v2/users/login",
        {"username": "pwduser", "password": "NewPass456"},
        format="json",
    )
    assert login_resp.status_code == 200
    # 旧密码应失败
    login_resp = api_client.post(
        "/api/v2/users/login",
        {"username": "pwduser", "password": "ValidPass123"},
        format="json",
    )
    assert login_resp.status_code == 401


@pytest.mark.django_db
def test_change_password_wrong_old(api_client, jwt_client):
    """修改密码：旧密码错误应失败（本人 JWT，见上方契约变更说明）"""
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "pwduser2", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    owner_client = jwt_client(User.objects.get(pk=user_id))
    response = owner_client.put(
        f"/api/v2/users/{user_id}/change_password",
        {"old_password": "WrongOld", "new_password": "NewPass456"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1005


@pytest.mark.django_db
def test_change_password_other_user_forbidden(api_client):
    """修改密码：管理员也不能改他人密码（返回 403）

    管理员改密码走 reset_password 接口，避免绕过旧密码校验的越权路径。
    """
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "pwduser3", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    response = api_client.put(
        f"/api/v2/users/{user_id}/change_password",
        {"old_password": "ValidPass123", "new_password": "NewPass456"},
        format="json",
    )
    assert response.status_code == 403
    # 原密码仍有效
    login_resp = api_client.post(
        "/api/v2/users/login",
        {"username": "pwduser3", "password": "ValidPass123"},
        format="json",
    )
    assert login_resp.status_code == 200


@pytest.mark.django_db
def test_list_users_forbidden_for_non_admin(api_client, jwt_client):
    """用户列表仅管理员可读（学生访问返回 403）"""
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "plerbuser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    student_client = jwt_client(User.objects.get(pk=user_id))
    response = student_client.get("/api/v2/users/list?page=1&page_size=10")
    assert response.status_code == 403


@pytest.mark.django_db
def test_reset_password(api_client):
    """重置密码（管理员用）"""
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "resetuser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    response = api_client.put(
        f"/api/v2/users/{user_id}/reset_password",
        {"new_password": "ResetNew123"},
        format="json",
    )
    assert response.status_code == 200
    # 用新密码登录
    login_resp = api_client.post(
        "/api/v2/users/login",
        {"username": "resetuser", "password": "ResetNew123"},
        format="json",
    )
    assert login_resp.status_code == 200


@pytest.mark.django_db
def test_delete_user(api_client):
    """删除用户"""
    create_resp = api_client.post(
        "/api/v2/users/create",
        {"username": "deleteuser", "password": "ValidPass123", "role": 1},
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    response = api_client.delete(f"/api/v2/users/{user_id}/delete")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 查询应返回 404
    get_resp = api_client.get(f"/api/v2/users/{user_id}")
    assert get_resp.status_code == 404
