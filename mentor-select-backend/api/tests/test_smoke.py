"""Smoke 接口测试

fixtures 由 api/tests/conftest.py 自动发现（不再 import-star 覆盖根 fixtures）。
"""
import pytest


@pytest.mark.django_db
def test_smoke_endpoint(api_client):
    """测试 GET /api/v2/smoke 返回 status=ok 与 DB 检测"""
    response = api_client.get("/api/v2/smoke")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["db"] == "ok"
    assert "db_latency_ms" in data["checks"]
    assert data["version"] == "v2"
