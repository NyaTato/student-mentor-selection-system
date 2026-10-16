"""Admin API 接口测试

fixtures 由 api/tests/conftest.py 自动发现（不再 import-star 覆盖根 fixtures）。
"""
import pytest


@pytest.mark.django_db
def test_create_admin_param_validation_short_password(api_client):
    """创建管理员参数校验：密码过短"""
    response = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "admin001",
            "password": "short",
            "name": "管理员",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


@pytest.mark.django_db
def test_create_admin_param_validation_missing_name(api_client):
    """创建管理员参数校验：缺少 name"""
    response = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "admin002",
            "password": "ValidPass123",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


@pytest.mark.django_db
def test_create_admin_success(api_client):
    """创建管理员成功（同时创建 User 和 Admin）"""
    response = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "admin010",
            "password": "ValidPass123",
            "name": "超级管理员",
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert "user_id" in data["data"]
    assert "admin_id" in data["data"]


@pytest.mark.django_db
def test_create_admin_duplicate_username(api_client):
    """重复用户名应失败"""
    payload = {
        "username": "dupadmin",
        "password": "ValidPass123",
        "name": "管理员",
    }
    api_client.post("/api/v2/admins/create", payload, format="json")
    response = api_client.post("/api/v2/admins/create", payload, format="json")
    assert response.status_code == 400
    assert response.json()["code"] == 1004


@pytest.mark.django_db
def test_get_admin_by_id(api_client):
    """按 ID 查询管理员"""
    create_resp = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "getadm",
            "password": "ValidPass123",
            "name": "查询测试",
        },
        format="json",
    )
    admin_id = create_resp.json()["data"]["admin_id"]
    response = api_client.get(f"/api/v2/admins/{admin_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["name"] == "查询测试"


@pytest.mark.django_db
def test_get_admin_by_user_id(api_client):
    """按 user_id 查询管理员"""
    create_resp = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "getadmbyuid",
            "password": "ValidPass123",
            "name": "测试",
        },
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    response = api_client.get(f"/api/v2/admins/by_user/{user_id}")
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "测试"


@pytest.mark.django_db
def test_get_admin_not_found(api_client):
    """查询不存在的管理员返回 404"""
    response = api_client.get("/api/v2/admins/99999")
    assert response.status_code == 404
    assert response.json()["code"] == 1003


@pytest.mark.django_db
def test_list_admins(api_client):
    """查询管理员列表"""
    for i in range(3):
        api_client.post(
            "/api/v2/admins/create",
            {
                "username": f"listadm{i}",
                "password": "ValidPass123",
                "name": f"管理员{i}",
            },
            format="json",
        )
    response = api_client.get("/api/v2/admins/list?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["total"] >= 3


@pytest.mark.django_db
def test_update_admin(api_client):
    """更新管理员信息"""
    create_resp = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "upadm",
            "password": "ValidPass123",
            "name": "原名",
        },
        format="json",
    )
    admin_id = create_resp.json()["data"]["admin_id"]
    response = api_client.put(
        f"/api/v2/admins/{admin_id}/update",
        {"name": "新名"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 验证更新
    get_resp = api_client.get(f"/api/v2/admins/{admin_id}")
    assert get_resp.json()["data"]["name"] == "新名"


@pytest.mark.django_db
def test_delete_admin(api_client):
    """删除管理员"""
    create_resp = api_client.post(
        "/api/v2/admins/create",
        {
            "username": "deladm",
            "password": "ValidPass123",
            "name": "测试",
        },
        format="json",
    )
    admin_id = create_resp.json()["data"]["admin_id"]
    response = api_client.delete(f"/api/v2/admins/{admin_id}/delete")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 查询应 404
    get_resp = api_client.get(f"/api/v2/admins/{admin_id}")
    assert get_resp.status_code == 404
