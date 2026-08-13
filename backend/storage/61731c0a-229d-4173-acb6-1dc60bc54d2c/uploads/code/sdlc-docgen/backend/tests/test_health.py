from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_template_list():
    resp = client.get("/api/v1/templates")
    assert resp.status_code == 200
    templates = resp.json()["templates"]
    assert any(t["template_id"] == "srs" for t in templates)
