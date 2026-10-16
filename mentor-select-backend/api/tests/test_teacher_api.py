"""Teacher API 接口测试

fixtures 由 api/tests/conftest.py 自动发现（不再 import-star 覆盖根 fixtures）。
"""
import pytest


@pytest.mark.django_db
def test_create_teacher_param_validation_short_password(api_client):
    """创建导师参数校验：密码过短"""
    response = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "teacher001",
            "password": "short",
            "teacher_number": "T20240001",
            "name": "张老师",
            "college": "计算机学院",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


@pytest.mark.django_db
def test_create_teacher_param_validation_missing_college(api_client):
    """创建导师参数校验：缺少 college"""
    response = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "teacher002",
            "password": "ValidPass123",
            "teacher_number": "T20240002",
            "name": "李老师",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


@pytest.mark.django_db
def test_create_teacher_success(api_client):
    """创建导师成功（同时创建 User 和 Teacher）"""
    response = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "teacher010",
            "password": "ValidPass123",
            "teacher_number": "T20240010",
            "name": "王老师",
            "college": "计算机学院",
            "title": "教授",
            "research_area": "人工智能",
            "profile": "研究方向为深度学习",
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert "user_id" in data["data"]
    assert "teacher_id" in data["data"]


@pytest.mark.django_db
def test_create_teacher_duplicate_username(api_client):
    """重复用户名应失败"""
    payload = {
        "username": "dupteacher",
        "password": "ValidPass123",
        "teacher_number": "T20240101",
        "name": "测试",
        "college": "计算机学院",
    }
    api_client.post("/api/v2/teachers/create", payload, format="json")
    response = api_client.post("/api/v2/teachers/create", payload, format="json")
    assert response.status_code == 400
    assert response.json()["code"] == 1004


@pytest.mark.django_db
def test_create_teacher_duplicate_teacher_number(api_client):
    """重复工号应失败"""
    api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "tn01",
            "password": "ValidPass123",
            "teacher_number": "DUPTN001",
            "name": "测试1",
            "college": "计算机学院",
        },
        format="json",
    )
    response = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "tn02",
            "password": "ValidPass123",
            "teacher_number": "DUPTN001",
            "name": "测试2",
            "college": "计算机学院",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1004


@pytest.mark.django_db
def test_get_teacher_by_id(api_client):
    """按 ID 查询导师"""
    create_resp = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "gettea",
            "password": "ValidPass123",
            "teacher_number": "GETTEA001",
            "name": "查询测试",
            "college": "计算机学院",
        },
        format="json",
    )
    teacher_id = create_resp.json()["data"]["teacher_id"]
    response = api_client.get(f"/api/v2/teachers/{teacher_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["teacher_number"] == "GETTEA001"
    assert data["data"]["name"] == "查询测试"


@pytest.mark.django_db
def test_get_teacher_by_user_id(api_client):
    """按 user_id 查询导师"""
    create_resp = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "getteabyuid",
            "password": "ValidPass123",
            "teacher_number": "TEABYUID001",
            "name": "测试",
            "college": "计算机学院",
        },
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    response = api_client.get(f"/api/v2/teachers/by_user/{user_id}")
    assert response.status_code == 200
    assert response.json()["data"]["teacher_number"] == "TEABYUID001"


@pytest.mark.django_db
def test_get_teacher_by_teacher_number(api_client):
    """按工号查询导师"""
    api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "getteabysn",
            "password": "ValidPass123",
            "teacher_number": "TEABYSN001",
            "name": "测试",
            "college": "计算机学院",
        },
        format="json",
    )
    response = api_client.get("/api/v2/teachers/by_number/TEABYSN001")
    assert response.status_code == 200
    assert response.json()["data"]["teacher_number"] == "TEABYSN001"


@pytest.mark.django_db
def test_get_teacher_not_found(api_client):
    """查询不存在的导师返回 404"""
    response = api_client.get("/api/v2/teachers/99999")
    assert response.status_code == 404
    assert response.json()["code"] == 1003


@pytest.mark.django_db
def test_list_teachers(api_client):
    """查询导师列表"""
    for i in range(3):
        api_client.post(
            "/api/v2/teachers/create",
            {
                "username": f"listtea{i}",
                "password": "ValidPass123",
                "teacher_number": f"LISTTEA{i:03d}",
                "name": f"导师{i}",
                "college": "计算机学院",
            },
            format="json",
        )
    response = api_client.get("/api/v2/teachers/list?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["total"] >= 3


@pytest.mark.django_db
def test_update_teacher(api_client):
    """更新导师信息"""
    create_resp = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "updtea",
            "password": "ValidPass123",
            "teacher_number": "UPDTEA001",
            "name": "原名",
            "college": "计算机学院",
        },
        format="json",
    )
    teacher_id = create_resp.json()["data"]["teacher_id"]
    response = api_client.put(
        f"/api/v2/teachers/{teacher_id}/update",
        {"name": "新名", "title": "副教授", "research_area": "机器学习"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 验证更新
    get_resp = api_client.get(f"/api/v2/teachers/{teacher_id}")
    assert get_resp.json()["data"]["name"] == "新名"
    assert get_resp.json()["data"]["title"] == "副教授"
    assert get_resp.json()["data"]["research_area"] == "机器学习"


@pytest.mark.django_db
def test_delete_teacher(api_client):
    """删除导师"""
    create_resp = api_client.post(
        "/api/v2/teachers/create",
        {
            "username": "deltea",
            "password": "ValidPass123",
            "teacher_number": "DELTEA001",
            "name": "测试",
            "college": "计算机学院",
        },
        format="json",
    )
    teacher_id = create_resp.json()["data"]["teacher_id"]
    response = api_client.delete(f"/api/v2/teachers/{teacher_id}/delete")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 查询应 404
    get_resp = api_client.get(f"/api/v2/teachers/{teacher_id}")
    assert get_resp.status_code == 404
