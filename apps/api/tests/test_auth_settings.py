import pytest

from app.auth import Settings


@pytest.mark.parametrize("environment", ["dev", "prod"])
@pytest.mark.parametrize("configured, expected", [(None, True), ("true", True), ("false", False)])
def test_registration_policy_and_public_config(monkeypatch, environment, configured, expected):
    from fastapi.testclient import TestClient
    from app.main import create_app

    monkeypatch.setenv("SELFLORE_ENV", environment)
    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "https://selflore.example")
    monkeypatch.setenv("SELFLORE_THROTTLE_KEY", "test-only-key")
    monkeypatch.delenv("SELFLORE_ALLOW_INSECURE_HTTP", raising=False)
    if configured is None:
        monkeypatch.delenv("SELFLORE_ALLOW_REGISTRATION", raising=False)
    else:
        monkeypatch.setenv("SELFLORE_ALLOW_REGISTRATION", configured)

    assert Settings().allow_registration is expected
    with TestClient(create_app()) as http:
        response = http.get("/api/auth/config")
        assert response.status_code == 200
        assert response.json() == {"registration_enabled": expected}


def test_production_rejects_http_by_default(monkeypatch):
    monkeypatch.setenv("SELFLORE_ENV", "prod")
    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "http://127.0.0.1:24566")
    monkeypatch.setenv("SELFLORE_THROTTLE_KEY", "test-only-key")
    monkeypatch.delenv("SELFLORE_ALLOW_INSECURE_HTTP", raising=False)

    with pytest.raises(RuntimeError, match="HTTPS Origin"):
        Settings()


def test_explicit_production_http_uses_separate_nonsecure_cookie(monkeypatch):
    monkeypatch.setenv("SELFLORE_ENV", "prod")
    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "http://127.0.0.1:24566")
    monkeypatch.setenv("SELFLORE_THROTTLE_KEY", "test-only-key")
    monkeypatch.setenv("SELFLORE_ALLOW_INSECURE_HTTP", "true")

    settings = Settings()
    assert settings.cookie_name == "selflore_session_http"
    assert settings.secure_cookie is False

    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "https://selflore.example")
    with pytest.raises(RuntimeError, match="HTTP Origin"):
        Settings()


def test_production_https_keeps_host_cookie(monkeypatch):
    monkeypatch.setenv("SELFLORE_ENV", "prod")
    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "https://selflore.example")
    monkeypatch.setenv("SELFLORE_THROTTLE_KEY", "test-only-key")
    monkeypatch.delenv("SELFLORE_ALLOW_INSECURE_HTTP", raising=False)

    settings = Settings()
    assert settings.cookie_name == "__Host-selflore_session"
    assert settings.secure_cookie is True
