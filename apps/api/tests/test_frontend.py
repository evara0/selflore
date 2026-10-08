from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_built_frontend_is_served_without_frontend_server(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text('<script src="/assets/app.js"></script>', encoding="utf-8")
    (assets / "app.js").write_text("window.selflore = true", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")

    client = TestClient(create_app(dist))

    assert client.get("/").status_code == 200
    assert "/assets/app.js" in client.get("/").text
    assert client.get("/assets/app.js").text == "window.selflore = true"
    assert client.get("/favicon.svg").status_code == 200
    assert client.get("/journal").text == client.get("/").text
    assert client.get("/api/health").json() == {"ok": True}


def test_unknown_api_and_missing_assets_do_not_return_frontend(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>SelfLore</h1>", encoding="utf-8")

    client = TestClient(create_app(dist))

    for path in ("/api", "/api/missing", "/assets/missing.js", "/missing.svg"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert "SelfLore" not in response.text


def test_frontend_is_not_mounted_before_build(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "missing"))

    assert client.get("/api/health").json() == {"ok": True}
    assert client.get("/").status_code == 404


def test_path_outside_build_directory_is_not_served(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>SelfLore</h1>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("private", encoding="utf-8")

    client = TestClient(create_app(dist))
    response = client.get("/%2e%2e/private.txt")

    assert response.status_code == 404
    assert "private" not in response.text
    assert "SelfLore" not in response.text
