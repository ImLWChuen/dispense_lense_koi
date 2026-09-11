from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200_and_expected_payload():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "ok",
        "service": "dispense-lens-api",
        "version": "0.1.0",
    }


def test_health_endpoint_present_in_openapi_schema():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/v1/health" in schema["paths"]
    health_path = schema["paths"]["/api/v1/health"]
    assert "get" in health_path
    get_op = health_path["get"]
    assert "200" in get_op["responses"]
