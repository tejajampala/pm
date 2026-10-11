from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import configure_static


def test_frontend_root_serves_generated_index(tmp_path):
    static_dir = tmp_path / "frontend" / "out"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        "<html><body><h1>Kanban Studio</h1></body></html>", encoding="utf-8"
    )
    (static_dir / "_next").mkdir()

    app = FastAPI()
    configure_static(app, static_dir)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Kanban Studio" in response.text
