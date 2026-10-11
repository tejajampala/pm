from fastapi import FastAPI
from helpers import client
from starlette.testclient import TestClient

from app.main import configure_static
from app.routes import router


def test_frontend_root_serves_generated_index(tmp_path):
    static_dir = tmp_path / "frontend" / "out"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        "<html><body><h1>Kanban Studio</h1></body></html>", encoding="utf-8"
    )
    (static_dir / "_next").mkdir()

    app = FastAPI()
    configure_static(app, static_dir)

    with TestClient(app) as static_client:
        response = static_client.get("/")

    assert response.status_code == 200
    assert "Kanban Studio" in response.text


def test_placeholder_page_is_served_when_no_frontend_build_exists(tmp_path):
    app = FastAPI()
    configure_static(app, tmp_path / "missing")

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "No frontend build found" in response.text


def test_static_mount_does_not_shadow_api_routes(tmp_path):
    (tmp_path / "index.html").write_text("<h1>site</h1>", encoding="utf-8")
    app = FastAPI()
    app.include_router(router)
    configure_static(app, tmp_path)

    response = TestClient(app).get("/api/health")

    assert response.json()["status"] == "ok"


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
