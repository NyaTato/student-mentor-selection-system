"""Student API 接口测试

fixtures 由 api/tests/conftest.py 自动发现（不再 import-star 覆盖根 fixtures）。
"""
import pytest


@pytest.mark.django_db
def test_create_student_param_validation_short_password(api_client):
    """创建学生参数校验：密码过短应返回 400"""
    response = api_client.post(
        "/api/v2/students/create",
        {
            "username": "student001",
            "password": "short",
            "student_number": "S20240001",
            "name": "张三",
            "major": "计算机科学",
            "class_name": "计科2401",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


@pytest.mark.django_db
def test_create_student_param_validation_missing_field(api_client):
    """创建学生参数校验：缺少 major 应返回 400"""
    response = api_client.post(
        "/api/v2/students/create",
        {
            "username": "student002",
            "password": "ValidPass123",
            "student_number": "S20240002",
            "name": "李四",
            "class_name": "计科2401",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1001


@pytest.mark.django_db
def test_create_student_success(api_client):
    """创建学生成功（同时创建 User 和 Student）"""
    response = api_client.post(
        "/api/v2/students/create",
        {
            "username": "student010",
            "password": "ValidPass123",
            "student_number": "S20240010",
            "name": "王五",
            "major": "软件工程",
            "class_name": "软工2401",
            "phone": "13800000000",
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert "user_id" in data["data"]
    assert "student_id" in data["data"]


@pytest.mark.django_db
def test_create_student_duplicate_username(api_client):
    """重复用户名应失败"""
    payload = {
        "username": "dupstudent",
        "password": "ValidPass123",
        "student_number": "S20240101",
        "name": "测试",
        "major": "计算机",
        "class_name": "计科2401",
    }
    api_client.post("/api/v2/students/create", payload, format="json")
    response = api_client.post("/api/v2/students/create", payload, format="json")
    assert response.status_code == 400
    assert response.json()["code"] == 1004


@pytest.mark.django_db
def test_create_student_duplicate_student_number(api_client):
    """重复学号应失败"""
    api_client.post(
        "/api/v2/students/create",
        {
            "username": "sn01",
            "password": "ValidPass123",
            "student_number": "DUPSN001",
            "name": "测试1",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    response = api_client.post(
        "/api/v2/students/create",
        {
            "username": "sn02",
            "password": "ValidPass123",
            "student_number": "DUPSN001",
            "name": "测试2",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1004


@pytest.mark.django_db
def test_get_student_by_id(api_client):
    """按 ID 查询学生"""
    create_resp = api_client.post(
        "/api/v2/students/create",
        {
            "username": "getstu",
            "password": "ValidPass123",
            "student_number": "GETSTU001",
            "name": "查询测试",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    student_id = create_resp.json()["data"]["student_id"]
    response = api_client.get(f"/api/v2/students/{student_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["student_number"] == "GETSTU001"
    assert data["data"]["name"] == "查询测试"


@pytest.mark.django_db
def test_get_student_by_user_id(api_client):
    """按 user_id 查询学生"""
    create_resp = api_client.post(
        "/api/v2/students/create",
        {
            "username": "getbyuid",
            "password": "ValidPass123",
            "student_number": "BYUID001",
            "name": "测试",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    user_id = create_resp.json()["data"]["user_id"]
    response = api_client.get(f"/api/v2/students/by_user/{user_id}")
    assert response.status_code == 200
    assert response.json()["data"]["student_number"] == "BYUID001"


@pytest.mark.django_db
def test_get_student_by_student_number(api_client):
    """按学号查询学生"""
    api_client.post(
        "/api/v2/students/create",
        {
            "username": "getbysn",
            "password": "ValidPass123",
            "student_number": "BYSN001",
            "name": "测试",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    response = api_client.get("/api/v2/students/by_number/BYSN001")
    assert response.status_code == 200
    assert response.json()["data"]["student_number"] == "BYSN001"


@pytest.mark.django_db
def test_get_student_not_found(api_client):
    """查询不存在的学生返回 404"""
    response = api_client.get("/api/v2/students/99999")
    assert response.status_code == 404
    assert response.json()["code"] == 1003


@pytest.mark.django_db
def test_list_students(api_client):
    """查询学生列表"""
    for i in range(3):
        api_client.post(
            "/api/v2/students/create",
            {
                "username": f"liststu{i}",
                "password": "ValidPass123",
                "student_number": f"LISTSTU{i:03d}",
                "name": f"学生{i}",
                "major": "计算机",
                "class_name": "计科2401",
            },
            format="json",
        )
    response = api_client.get("/api/v2/students/list?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["total"] >= 3


@pytest.mark.django_db
def test_update_student(api_client):
    """更新学生信息"""
    create_resp = api_client.post(
        "/api/v2/students/create",
        {
            "username": "updstu",
            "password": "ValidPass123",
            "student_number": "UPDSTU001",
            "name": "原名",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    student_id = create_resp.json()["data"]["student_id"]
    response = api_client.put(
        f"/api/v2/students/{student_id}/update",
        {"name": "新名", "major": "软件工程"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 验证更新
    get_resp = api_client.get(f"/api/v2/students/{student_id}")
    assert get_resp.json()["data"]["name"] == "新名"
    assert get_resp.json()["data"]["major"] == "软件工程"


@pytest.mark.django_db
def test_update_student_phone(api_client):
    """更新学生电话"""
    create_resp = api_client.post(
        "/api/v2/students/create",
        {
            "username": "phonestu",
            "password": "ValidPass123",
            "student_number": "PHONESTU001",
            "name": "测试",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    student_id = create_resp.json()["data"]["student_id"]
    response = api_client.put(
        f"/api/v2/students/{student_id}/phone",
        {"phone": "13900000000"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 验证
    get_resp = api_client.get(f"/api/v2/students/{student_id}")
    assert get_resp.json()["data"]["phone"] == "13900000000"


@pytest.mark.django_db
def test_delete_student(api_client):
    """删除学生"""
    create_resp = api_client.post(
        "/api/v2/students/create",
        {
            "username": "delstu",
            "password": "ValidPass123",
            "student_number": "DELSTU001",
            "name": "测试",
            "major": "计算机",
            "class_name": "计科2401",
        },
        format="json",
    )
    student_id = create_resp.json()["data"]["student_id"]
    response = api_client.delete(f"/api/v2/students/{student_id}/delete")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    # 查询应 404
    get_resp = api_client.get(f"/api/v2/students/{student_id}")
    assert get_resp.status_code == 404
