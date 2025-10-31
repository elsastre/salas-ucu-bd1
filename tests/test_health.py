from fastapi.testclient import TestClient
from src.app import app
client = TestClient(app)

def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()
