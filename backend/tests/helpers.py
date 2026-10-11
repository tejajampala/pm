from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def board() -> dict:
    return client.get("/api/users/user/board").json()
