from __future__ import annotations

import pytest

from app import db_bootstrap


def test_target_names_are_environment_scoped() -> None:
    dev = db_bootstrap.Target("dev", "127.0.0.1", 5432, "postgres")
    prod = db_bootstrap.Target("prod", "127.0.0.1", 6171, "postgres")

    assert (dev.database, dev.owner, dev.migrator, dev.app) == (
        "selflore_dev",
        "selflore_dev_owner",
        "selflore_dev_migrator",
        "selflore_dev_app",
    )
    assert prod.database == "selflore_prod"
    assert prod.owner != dev.owner


@pytest.mark.parametrize("port", ["0", "65536"])
def test_invalid_port_is_rejected_before_connection(monkeypatch, port: str) -> None:
    def fail_connect(*args, **kwargs):
        raise AssertionError("should not connect")

    monkeypatch.setattr(db_bootstrap.psycopg, "connect", fail_connect)
    with pytest.raises(SystemExit) as result:
        db_bootstrap.main(["--env", "dev", "--host", "127.0.0.1", "--port", port, "--admin-user", "postgres"])
    assert result.value.code == 2


def test_existing_privileged_login_role_is_rejected() -> None:
    with pytest.raises(db_bootstrap.BootstrapError, match="高级权限"):
        db_bootstrap._check_role(
            "selflore_prod_app", (True, True, False, False, False, False, True), login=True
        )


def test_existing_login_without_password_is_rejected() -> None:
    with pytest.raises(db_bootstrap.BootstrapError, match="没有密码"):
        db_bootstrap._check_role(
            "selflore_prod_app", (True, False, False, False, False, False, False), login=True
        )


def test_existing_database_with_different_owner_is_rejected() -> None:
    with pytest.raises(db_bootstrap.BootstrapError, match="所有者"):
        db_bootstrap._check_database(
            "selflore_prod", ("postgres", "UTF8"), "selflore_prod_owner"
        )


def test_noninteractive_password_requires_secret_input(monkeypatch) -> None:
    monkeypatch.delenv("SELFLORE_APP_PASSWORD", raising=False)
    monkeypatch.setattr(db_bootstrap.sys.stdin, "isatty", lambda: False)
    with pytest.raises(db_bootstrap.BootstrapError, match="SELFLORE_APP_PASSWORD"):
        db_bootstrap._password("app", "SELFLORE_APP_PASSWORD")


def test_password_from_environment_is_not_printed(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SELFLORE_APP_PASSWORD", "sample-secret")
    assert db_bootstrap._password("app", "SELFLORE_APP_PASSWORD") == "sample-secret"
    assert capsys.readouterr() == ("", "")


def test_effective_create_privilege_is_rejected(monkeypatch) -> None:
    def fake_one(connection, query, values=()):
        return (True, True, True, False, False, True) + (False,) * 6

    monkeypatch.setattr(db_bootstrap, "_one", fake_one)
    target = db_bootstrap.Target("prod", "127.0.0.1", 6171, "postgres")
    with pytest.raises(db_bootstrap.BootstrapError, match="有效权限"):
        db_bootstrap._verify_privileges(object(), target)


def test_app_write_privilege_is_rejected(monkeypatch) -> None:
    def fake_one(connection, query, values=()):
        return (True, False, True, False, False, True, True) + (False,) * 5

    monkeypatch.setattr(db_bootstrap, "_one", fake_one)
    target = db_bootstrap.Target("prod", "127.0.0.1", 6171, "postgres")
    with pytest.raises(db_bootstrap.BootstrapError, match="有效权限"):
        db_bootstrap._verify_privileges(object(), target)


def test_migrator_must_be_able_to_set_owner(monkeypatch) -> None:
    def fake_one(connection, query, values=()):
        if "pg_has_role" in query:
            return (False, False)
        return (True, False, True, False, False, True) + (False,) * 6

    monkeypatch.setattr(db_bootstrap, "_one", fake_one)
    target = db_bootstrap.Target("prod", "127.0.0.1", 6171, "postgres")
    with pytest.raises(db_bootstrap.BootstrapError, match="owner 成员权限"):
        db_bootstrap._verify_privileges(object(), target)


def test_existing_table_with_extra_column_is_rejected(monkeypatch) -> None:
    class FakeCursor:
        def __init__(self):
            self.query_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, query, values):
            self.query_count += 1

        def fetchall(self):
            if self.query_count == 1:
                return [("id", "bigint", True, False, "", ""), ("other", "text", False, False, "", "")]
            return [("p", True, False, False)]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(db_bootstrap, "_table", lambda connection: (1, "r", "selflore_dev_owner"))
    with pytest.raises(db_bootstrap.BootstrapError, match="列或主键"):
        db_bootstrap._check_table(FakeConnection(), "selflore_dev_owner")


def test_postgresql_18_not_null_constraint_allows_reentry(monkeypatch) -> None:
    class FakeCursor:
        def __init__(self):
            self.query_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, query, values):
            self.query_count += 1
            if self.query_count == 2:
                assert "contype <> 'n'" in query

        def fetchall(self):
            if self.query_count == 1:
                return [("id", "bigint", True, False, "", "")]
            return [("p", True, False, False)]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(db_bootstrap, "_table", lambda connection: (1, "r", "selflore_dev_owner"))
    db_bootstrap._check_table(FakeConnection(), "selflore_dev_owner")
