import os

os.environ["DATABASE_URL"] = "sqlite:///./test_khmerhire.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_categories_have_ten_top_level_groups():
    response = client.get("/categories")
    assert response.status_code == 200
    assert len(response.json()) == 10
