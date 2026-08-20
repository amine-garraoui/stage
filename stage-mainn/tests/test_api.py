import os

os.environ["API_KEYS"] = "test-api-key"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost"

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_is_public() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_requires_api_key() -> None:
    response = client.get("/months")

    assert response.status_code == 401


def test_protected_route_accepts_configured_api_key() -> None:
    response = client.get(
        "/months",
        headers={"Authorization": "Bearer test-api-key"},
    )

    assert response.status_code != 401