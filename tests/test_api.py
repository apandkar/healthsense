from fastapi.testclient import TestClient
from app.main import app, ChatRequest

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200


def test_chat_requires_symptoms():
    response = client.post(
        "/chat",
        json={"location": "Chicago"}
    )

    assert response.status_code == 422


def test_location_is_optional():
    request = ChatRequest(symptoms="headache")

    assert request.symptoms == "headache"
    assert request.location == ""
