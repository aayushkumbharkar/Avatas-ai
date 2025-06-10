from fastapi.testclient import TestClient
from backend.app.main import app  # Adjust import path if necessary

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")  # Assuming /api prefix from main app
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
