"""Run only against an explicitly selected, disposable PostgreSQL test cluster."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest
from fastapi.testclient import TestClient

from app.admin_bootstrap import create_first_admin
from app.db_migrate import MIGRATIONS_DIR, MigrationError, migrate
from app.main import create_app


ORIGIN = {"Origin": "http://127.0.0.1:24566"}
PASSWORD = "a-long-test-password-123"
TEST_TABLES = "app.review_logs, app.review_states, app.review_units, app.activity_events, app.collection_items, app.card_links, app.card_tags, app.card_topics, app.cards, app.collections, app.tags, app.topics, app.user_profiles, app.account_audit, app.auth_sessions, app.auth_login_throttle, app.users"


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    app_dsn = os.environ.get("SELFLORE_TEST_APP_DSN")
    migrator_dsn = os.environ.get("SELFLORE_TEST_MIGRATOR_DSN")
    if not app_dsn or not migrator_dsn:
        pytest.skip("需要显式提供隔离数据库的测试 DSN")
    if os.environ.get("SELFLORE_TEST_ISOLATED") != "1":
        pytest.fail("破坏性集成测试仅允许显式标记的一次性数据库")
    for dsn, expected_user in ((app_dsn, "selflore_dev_app"), (migrator_dsn, "selflore_dev_migrator")):
        info = conninfo_to_dict(dsn)
        if (info.get("host"), info.get("port"), info.get("dbname"), info.get("user")) != (
            "127.0.0.1", "6179", "selflore_dev", expected_user
        ):
            pytest.fail("集成测试 DSN 必须指向 127.0.0.1:6179 的隔离 selflore_dev")
    monkeypatch.setenv("SELFLORE_DATABASE_URL", app_dsn)
    monkeypatch.setenv("SELFLORE_ALLOW_REGISTRATION", "true")
    monkeypatch.setenv("SELFLORE_ENV", "dev")
    with psycopg.connect(migrator_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE selflore_dev_owner")
            cursor.execute("TRUNCATE " + TEST_TABLES)
    yield
    with psycopg.connect(migrator_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE selflore_dev_owner")
            cursor.execute("TRUNCATE " + TEST_TABLES)


def client() -> TestClient:
    return TestClient(create_app())


def register(http: TestClient, username: str = "alice"):
    return http.post("/api/auth/register", json={"username": username, "password": PASSWORD}, headers=ORIGIN)


def login(http: TestClient, username: str = "alice", password: str = PASSWORD):
    return http.post("/api/auth/login", json={"username": username, "password": password}, headers=ORIGIN)


def csrf(http: TestClient) -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": http.get("/api/auth/me").json()["csrf_token"]}


def test_registration_login_logout_and_csrf():
    with client() as http:
        assert register(http, "Alice").status_code == 201
        assert register(http, "alice").status_code == 409
        assert http.post("/api/auth/register", json={"username": "mallory", "password": PASSWORD, "role": "admin"}, headers=ORIGIN).status_code == 422
        assert http.post("/api/auth/register", json={"username": "short", "password": "short"}, headers=ORIGIN).status_code == 422
        assert http.get("/api/auth/me").status_code == 401
        assert login(http).status_code == 200
        current = http.get("/api/auth/me")
        assert current.status_code == 200
        assert current.json()["username"] == "alice"
        assert "password_hash" not in current.text
        assert http.post(
            "/api/auth/change-password",
            json={"current_password": PASSWORD, "new_password": "new-test-password-123", "user_id": "somebody-else"},
            headers=csrf(http),
        ).status_code == 422
        assert http.post("/api/auth/logout", headers=ORIGIN).status_code == 403
        assert http.post("/api/auth/logout", headers=csrf(http)).status_code == 204
        assert http.get("/api/auth/me").status_code == 401


def test_origin_password_change_and_session_revocation():
    with client() as http:
        assert http.post("/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert register(http).status_code == 201
        assert login(http).status_code == 200
        headers = csrf(http)
        assert http.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": "new-test-password-123"}, headers=headers).status_code == 400
        assert http.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "new-test-password-123"}, headers=headers).status_code == 204
        assert http.get("/api/auth/me").status_code == 401
        assert login(http).status_code == 401
        assert login(http, password="new-test-password-123").status_code == 200


def test_admin_permissions_and_last_admin(capsys):
    create_first_admin("dev", "127.0.0.1", 6179, "keeper", PASSWORD)
    assert PASSWORD not in capsys.readouterr().out
    with pytest.raises(RuntimeError, match="已存在"):
        create_first_admin("dev", "127.0.0.1", 6179, "another", PASSWORD)
    with client() as http:
        assert register(http).status_code == 201
        assert http.get("/api/admin/users").status_code == 401
        assert login(http).status_code == 200
        assert http.get("/api/admin/users").status_code == 403
    with client() as admin:
        assert login(admin, "keeper").status_code == 200
        listing = admin.get("/api/admin/users")
        assert listing.status_code == 200
        assert listing.json()["total"] == 2
        assert "password_hash" not in listing.text
        keeper = next(item for item in listing.json()["items"] if item["username"] == "keeper")
        alice = next(item for item in listing.json()["items"] if item["username"] == "alice")
        assert admin.patch(f"/api/admin/users/{keeper['id']}", json={"role": "member"}, headers=csrf(admin)).status_code == 409
        assert admin.patch(f"/api/admin/users/{alice['id']}", json={"is_active": False}, headers=csrf(admin)).status_code == 200
        assert login(client()).status_code == 401
        created = admin.post("/api/admin/users", json={"username": "bob", "password": PASSWORD}, headers=csrf(admin))
        assert created.status_code == 201
        assert created.json()["role"] == "member"


def test_concurrent_admin_demotions_keep_one_admin():
    create_first_admin("dev", "127.0.0.1", 6179, "keeper", PASSWORD)
    with client() as keeper:
        assert login(keeper, "keeper").status_code == 200
        created = keeper.post("/api/admin/users", json={"username": "second", "password": PASSWORD}, headers=csrf(keeper)).json()
        assert keeper.patch(f"/api/admin/users/{created['id']}", json={"role": "admin"}, headers=csrf(keeper)).status_code == 200
        keeper_id = keeper.get("/api/auth/me").json()["id"]
        keeper_csrf = csrf(keeper)
        with client() as second:
            assert login(second, "second").status_code == 200
            second_csrf = csrf(second)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [
                    pool.submit(keeper.patch, f"/api/admin/users/{keeper_id}", json={"role": "member"}, headers=keeper_csrf),
                    pool.submit(second.patch, f"/api/admin/users/{created['id']}", json={"role": "member"}, headers=second_csrf),
                ]
                assert sorted(result.result().status_code for result in results) == [200, 409]
    with psycopg.connect(os.environ["SELFLORE_TEST_APP_DSN"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM app.users WHERE role = 'admin' AND is_active")
            assert cursor.fetchone()[0] == 1


def test_login_throttle_is_persistent():
    with client() as http:
        assert register(http).status_code == 201
        for _ in range(5):
            assert login(http, password="wrong").status_code == 401
        assert login(http).status_code == 429
    with client() as another_worker:
        assert login(another_worker).status_code == 429


def test_disabled_account_invalidates_existing_session():
    create_first_admin("dev", "127.0.0.1", 6179, "keeper", PASSWORD)
    with client() as member, client() as admin:
        assert register(member).status_code == 201
        assert login(member).status_code == 200
        assert login(admin, "keeper").status_code == 200
        member_id = member.get("/api/auth/me").json()["id"]
        assert admin.patch(f"/api/admin/users/{member_id}", json={"is_active": False}, headers=csrf(admin)).status_code == 200
        assert member.get("/api/auth/me").status_code == 401


def test_registration_toggle_and_production_cookie(monkeypatch):
    monkeypatch.setenv("SELFLORE_ALLOW_REGISTRATION", "false")
    with client() as http:
        assert http.get("/api/auth/config").json() == {"registration_enabled": False}
        assert register(http).status_code == 403
    create_first_admin("dev", "127.0.0.1", 6179, "keeper", PASSWORD)
    monkeypatch.setenv("SELFLORE_ENV", "prod")
    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "https://selflore.example")
    monkeypatch.setenv("SELFLORE_THROTTLE_KEY", "isolated-test-throttle-key")
    with client() as http:
        result = http.post("/api/auth/login", json={"username": "keeper", "password": PASSWORD}, headers={"Origin": "https://selflore.example"})
        assert result.status_code == 200
        cookie = result.headers["set-cookie"]
        assert "__Host-selflore_session=" in cookie
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Path=/" in cookie and "Domain=" not in cookie


def test_explicit_production_http_login_uses_separate_cookie(monkeypatch):
    create_first_admin("dev", "127.0.0.1", 6179, "keeper", PASSWORD)
    monkeypatch.setenv("SELFLORE_ENV", "prod")
    monkeypatch.setenv("SELFLORE_ALLOWED_ORIGINS", "http://127.0.0.1:24566")
    monkeypatch.setenv("SELFLORE_THROTTLE_KEY", "isolated-test-throttle-key")
    monkeypatch.setenv("SELFLORE_ALLOW_INSECURE_HTTP", "true")
    with client() as http:
        result = http.post("/api/auth/login", json={"username": "keeper", "password": PASSWORD}, headers=ORIGIN)
        assert result.status_code == 200
        cookie = result.headers["set-cookie"]
        assert "selflore_session_http=" in cookie
        assert "Secure" not in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert http.get("/api/auth/me").json()["username"] == "keeper"


def test_migration_history_rollback_and_app_privileges(tmp_path: Path):
    assert migrate("dev", "127.0.0.1", 6179) == []
    first = MIGRATIONS_DIR / "0001_identity.sql"
    (tmp_path / first.name).write_bytes(first.read_bytes() + b"\n-- changed\n")
    with pytest.raises(MigrationError, match="改动"):
        migrate("dev", "127.0.0.1", 6179, tmp_path)
    (tmp_path / first.name).write_bytes(first.read_bytes())
    for migration in MIGRATIONS_DIR.glob('*.sql'):
        (tmp_path / migration.name).write_bytes(migration.read_bytes())
    (tmp_path / "0004_fail.sql").write_text("CREATE TABLE app.should_rollback (id integer); SELECT 1/0;", encoding="utf-8")
    with pytest.raises(psycopg.Error):
        migrate("dev", "127.0.0.1", 6179, tmp_path)
    with psycopg.connect(os.environ["SELFLORE_TEST_MIGRATOR_DSN"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE selflore_dev_owner")
            cursor.execute("SELECT to_regclass('app.should_rollback')")
            assert cursor.fetchone()[0] is None
            cursor.execute("SELECT count(*) FROM app.schema_migrations WHERE version = '0004_fail'")
            assert cursor.fetchone()[0] == 0
    with psycopg.connect(os.environ["SELFLORE_TEST_APP_DSN"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT has_schema_privilege(current_user, 'app', 'CREATE'), has_table_privilege(current_user, 'app.schema_migrations', 'SELECT')")
            assert cursor.fetchone() == (False, False)
