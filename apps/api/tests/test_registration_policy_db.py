"""Policy migration and API checks in a newly created workspace-owned cluster."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
import pytest
from fastapi.testclient import TestClient

from app.auth import hasher
from app.db_bootstrap import Target, bootstrap
from app.db_migrate import MIGRATIONS_DIR, migrate
from app.main import create_app


@pytest.fixture(scope="module")
def policy_database(tmp_path_factory):
    if os.environ.get("SELFLORE_POLICY_TEST_ISOLATED") != "1":
        pytest.skip("需要新建的本项目临时 PostgreSQL 6180 实例")
    with psycopg.connect(host="127.0.0.1", port=6180, dbname="postgres", user="postgres") as db:
        data = Path(db.execute("SHOW data_directory").fetchone()[0]).resolve()
        allowed = Path(__file__).resolve().parents[3] / ".cache" / "registration-policy"
        assert data.is_relative_to(allowed.resolve())
        assert db.execute("SELECT to_regclass('app.users')").fetchone() == (None,)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SELFLORE_MIGRATOR_PASSWORD", str(uuid4()))
        patch.setenv("SELFLORE_APP_PASSWORD", str(uuid4()))
        bootstrap(Target("dev", "127.0.0.1", 6180, "postgres"))
        baseline = tmp_path_factory.mktemp("registration-baseline")
        (baseline / "0001_identity.sql").write_bytes((MIGRATIONS_DIR / "0001_identity.sql").read_bytes())
        assert migrate("dev", "127.0.0.1", 6180, baseline) == ["0001_identity"]
        with psycopg.connect(host="127.0.0.1", port=6180, dbname="selflore_dev", user="postgres") as db:
            db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'legacy',%s)", (uuid4(), hasher.hash("legacy-password")))
            before = db.execute("SELECT id, username, password_hash FROM app.users").fetchall()
        assert migrate("dev", "127.0.0.1", 6180) == ["0002_card_workspace", "0003_knowledge_review", "0004_relax_username"]
        assert migrate("dev", "127.0.0.1", 6180) == []
        with psycopg.connect(host="127.0.0.1", port=6180, dbname="selflore_dev", user="postgres") as db:
            assert db.execute("SELECT id, username, password_hash FROM app.users").fetchall() == before
        dsn = make_conninfo(host="127.0.0.1", port=6180, dbname="selflore_dev", user="selflore_dev_app", password=os.environ["SELFLORE_APP_PASSWORD"])
        patch.setenv("SELFLORE_DATABASE_URL", dsn)
        patch.setenv("SELFLORE_ENV", "dev")
        patch.setenv("SELFLORE_ALLOW_REGISTRATION", "true")
        patch.setenv("SELFLORE_ALLOWED_ORIGINS", "http://127.0.0.1:24566")
        yield dsn


def test_database_accepts_new_names_and_preserves_constraints(policy_database):
    with psycopg.connect(policy_database, autocommit=True) as db:
        for name in ["中文用户", "123用户", "-开头", "_开头", "a" * 32]:
            db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,%s,'test-only')", (uuid4(), name))
        for name in ["ab", "a" * 33, "a b", "a.b", "用户😀", "éab"]:
            with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.StringDataRightTruncation)):
                db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,%s,'test-only')", (uuid4(), name))
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'legacy','test-only')", (uuid4(),))


def test_real_registration_login_and_password_change(policy_database):
    origin = {"Origin": "http://127.0.0.1:24566"}
    with TestClient(create_app()) as http:
        assert http.post("/api/auth/login", json={"username": "LEGACY", "password": "legacy-password"}, headers=origin).status_code == 200
        for name in ["新中文账号", "123新用户"]:
            credentials = {"username": name, "password": "12345678"}
            response = http.post("/api/auth/register", json=credentials, headers=origin)
            assert response.status_code == 201, response.text
            assert http.post("/api/auth/login", json=credentials, headers=origin).status_code == 200
            current = http.get("/api/auth/me").json()
            assert current["username"] == name
        assert http.post("/api/auth/register", json={"username": "新中文账号", "password": "12345678"}, headers=origin).status_code == 409
        current = http.get("/api/auth/me").json()
        assert http.post("/api/auth/change-password", json={"current_password": "12345678", "new_password": "abcdefgh"}, headers={**origin, "X-CSRF-Token": current["csrf_token"]}).status_code == 204
        assert http.post("/api/auth/login", json={"username": "123新用户", "password": "abcdefgh"}, headers=origin).status_code == 200
