"""Initialize one SelfLore PostgreSQL environment without touching other databases."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from dataclasses import dataclass

import psycopg
from psycopg import sql


class BootstrapError(Exception):
    """A target is unsafe or incomplete for automatic initialization."""


@dataclass(frozen=True, repr=False)
class Target:
    environment: str
    host: str
    port: int
    admin_user: str
    admin_password: str | None = None

    @property
    def database(self) -> str:
        return f"selflore_{self.environment}"

    @property
    def owner(self) -> str:
        return f"selflore_{self.environment}_owner"

    @property
    def migrator(self) -> str:
        return f"selflore_{self.environment}_migrator"

    @property
    def app(self) -> str:
        return f"selflore_{self.environment}_app"

    def connect(self, database: str) -> psycopg.Connection:
        options = {
            "dbname": database,
            "user": self.admin_user,
            "port": self.port,
            "connect_timeout": 5,
            "autocommit": True,
        }
        options["host"] = self.host
        if self.admin_password is not None:
            options["password"] = self.admin_password
        return psycopg.connect(**options)


def _one(connection: psycopg.Connection, query: str, values: tuple = ()) -> tuple | None:
    with connection.cursor() as cursor:
        cursor.execute(query, values)
        return cursor.fetchone()


def _run(connection: psycopg.Connection, statement: sql.Composable | str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(statement)


def _password(label: str, env_name: str) -> str:
    value = os.environ.get(env_name)
    if value is not None:
        if not value:
            raise BootstrapError(f"{env_name} 已设置为空值")
        return value
    if not sys.stdin.isatty():
        raise BootstrapError(f"首次创建 {label} 需要 {env_name}，或在交互终端输入密码")
    first = getpass.getpass(f"{label} 密码: ")
    second = getpass.getpass(f"再次输入 {label} 密码: ")
    if not first or first != second:
        raise BootstrapError(f"{label} 密码为空或两次输入不一致")
    return first


def _role(connection: psycopg.Connection, name: str) -> tuple | None:
    return _one(
        connection,
        """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                  rolreplication, rolbypassrls, rolpassword IS NOT NULL
           FROM pg_catalog.pg_authid WHERE rolname = %s""",
        (name,),
    )


def _check_role(name: str, details: tuple | None, *, login: bool) -> None:
    if details is None:
        return
    if details[:6] != (login, False, False, False, False, False):
        raise BootstrapError(f"角色 {name} 的登录或高级权限与预期不符")
    if login and not details[6]:
        raise BootstrapError(f"角色 {name} 没有密码；不会覆盖现有角色")


def _database(connection: psycopg.Connection, name: str) -> tuple | None:
    return _one(
        connection,
        """SELECT pg_get_userbyid(datdba), pg_encoding_to_char(encoding)
           FROM pg_catalog.pg_database WHERE datname = %s""",
        (name,),
    )


def _check_database(name: str, details: tuple | None, owner: str) -> None:
    if details is not None and details != (owner, "UTF8"):
        raise BootstrapError(f"数据库 {name} 的所有者或编码与预期不符")


def _schema(connection: psycopg.Connection) -> str | None:
    found = _one(
        connection,
        """SELECT pg_get_userbyid(nspowner)
           FROM pg_catalog.pg_namespace WHERE nspname = 'app'""",
    )
    return found[0] if found else None


def _table(connection: psycopg.Connection) -> tuple | None:
    return _one(
        connection,
        """SELECT c.oid, c.relkind, pg_get_userbyid(c.relowner)
           FROM pg_catalog.pg_class c
           JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'app' AND c.relname = 'connection_probe'""",
    )


def _check_table(connection: psycopg.Connection, owner: str) -> None:
    found = _table(connection)
    if found is None:
        return
    oid, kind, actual_owner = found
    if kind != "r" or actual_owner != owner:
        raise BootstrapError("app.connection_probe 的类型或所有者与预期不符")
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT attname, atttypid::regtype::text, attnotnull,
                      atthasdef, attidentity::text, attgenerated::text
               FROM pg_catalog.pg_attribute
               WHERE attrelid = %s AND attnum > 0 AND NOT attisdropped
               ORDER BY attnum""",
            (oid,),
        )
        columns = cursor.fetchall()
        cursor.execute(
            """SELECT contype::text, conkey = ARRAY[1]::smallint[],
                      condeferrable, condeferred
               FROM pg_catalog.pg_constraint
               WHERE conrelid = %s AND contype <> 'n'""",
            (oid,),
        )
        keys = cursor.fetchall()
    if columns != [("id", "bigint", True, False, "", "")] or keys != [
        ("p", True, False, False)
    ]:
        raise BootstrapError(
            "app.connection_probe 的列或主键与预期不符："
            f"columns={columns!r}, constraints={keys!r}"
        )


def _membership(connection: psycopg.Connection, target: Target) -> tuple | None:
    return _one(
        connection,
        """SELECT m.admin_option, m.inherit_option, m.set_option
           FROM pg_catalog.pg_auth_members m
           JOIN pg_catalog.pg_roles parent ON parent.oid = m.roleid
           JOIN pg_catalog.pg_roles child ON child.oid = m.member
           WHERE parent.rolname = %s AND child.rolname = %s""",
        (target.owner, target.migrator),
    )


def _check_membership(connection: psycopg.Connection, target: Target) -> None:
    membership = _membership(connection, target)
    if membership is not None and membership != (False, False, True):
        raise BootstrapError("migrator 到 owner 的成员关系与预期不符")
    app_member = _one(
        connection,
        "SELECT pg_has_role(%s::name, %s::text, 'MEMBER')",
        (target.app, target.owner),
    ) if _role(connection, target.app) and _role(connection, target.owner) else None
    if app_member and app_member[0]:
        raise BootstrapError("app 角色已是 owner 的成员")


def _preflight_target(connection: psycopg.Connection, target: Target) -> None:
    schema_owner = _schema(connection)
    if schema_owner is not None and schema_owner != target.owner:
        raise BootstrapError("app schema 已存在，但不是目标 owner 持有")
    _check_table(connection, target.owner)
    if _role(connection, target.app):
        can_create_database = _one(
            connection,
            "SELECT has_database_privilege(%s::name, current_database(), 'CREATE')",
            (target.app,),
        )
        can_create_public = _one(
            connection,
            "SELECT has_schema_privilege(%s::name, 'public', 'CREATE')",
            (target.app,),
        )
        can_create_app = _one(
            connection,
            "SELECT has_schema_privilege(%s::name, 'app', 'CREATE')",
            (target.app,),
        ) if schema_owner is not None else None
        if any(result and result[0] for result in (
            can_create_database, can_create_public, can_create_app
        )):
            raise BootstrapError("app 角色已具有建库对象或建表权限")


def _verify_privileges(connection: psycopg.Connection, target: Target) -> None:
    result = _one(
        connection,
        """SELECT has_database_privilege(%s::name, current_database(), 'CONNECT'),
                  has_database_privilege(%s::name, current_database(), 'CREATE'),
                  has_schema_privilege(%s::name, 'app', 'USAGE'),
                  has_schema_privilege(%s::name, 'app', 'CREATE'),
                  has_schema_privilege(%s::name, 'public', 'CREATE'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'SELECT'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'INSERT'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'UPDATE'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'DELETE'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'TRUNCATE'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'REFERENCES'),
                  has_table_privilege(%s::name, 'app.connection_probe', 'TRIGGER')""",
        (target.app,) * 12,
    )
    if result != (True, False, True, False, False, True) + (False,) * 6:
        raise BootstrapError("app 角色的有效权限与预期不符")
    role_access = _one(
        connection,
        """SELECT pg_has_role(%s::name, %s::name, 'SET'),
                  pg_has_role(%s::name, %s::name, 'MEMBER')""",
        (target.migrator, target.owner, target.app, target.owner),
    )
    if role_access != (True, False):
        raise BootstrapError("migrator 或 app 的 owner 成员权限与预期不符")


def bootstrap(target: Target) -> None:
    with target.connect("postgres") as admin:
        print(
            f"连接目标: {admin.info.host}:{admin.info.port}/{target.database} "
            f"({target.environment})"
        )
        identity = _one(
            admin,
            "SELECT current_setting('server_version_num')::integer, rolsuper "
            "FROM pg_catalog.pg_roles WHERE rolname = current_user",
        )
        if identity is None or identity[0] // 10000 != 18:
            raise BootstrapError("目标服务器必须是 PostgreSQL 18")
        if not identity[1]:
            raise BootstrapError("首次初始化需要 PostgreSQL 超级用户连接")

        roles = {
            target.owner: _role(admin, target.owner),
            target.migrator: _role(admin, target.migrator),
            target.app: _role(admin, target.app),
        }
        _check_role(target.owner, roles[target.owner], login=False)
        _check_role(target.migrator, roles[target.migrator], login=True)
        _check_role(target.app, roles[target.app], login=True)
        _check_membership(admin, target)
        existing_database = _database(admin, target.database)
        _check_database(target.database, existing_database, target.owner)

        if existing_database:
            with target.connect(target.database) as existing:
                _preflight_target(existing, target)

        passwords = {}
        if roles[target.migrator] is None:
            passwords[target.migrator] = _password(
                "migrator", "SELFLORE_MIGRATOR_PASSWORD"
            )
        if roles[target.app] is None:
            passwords[target.app] = _password("app", "SELFLORE_APP_PASSWORD")

        if roles[target.owner] is None:
            _run(admin, sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(sql.Identifier(target.owner)))
            print(f"已创建角色: {target.owner}")
        for role in (target.migrator, target.app):
            if roles[role] is None:
                _run(
                    admin,
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(passwords[role])
                    ),
                )
                print(f"已创建角色: {role}")
        if _membership(admin, target) is None:
            _run(
                admin,
                sql.SQL("GRANT {} TO {} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(target.owner), sql.Identifier(target.migrator)
                ),
            )
            print(f"已授予 owner 切换权限: {target.migrator}")
        if existing_database is None:
            _run(
                admin,
                sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(target.database), sql.Identifier(target.owner)
                ),
            )
            print(f"已创建数据库: {target.database}")
        _run(
            admin,
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(target.database)
            ),
        )
        _run(
            admin,
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
                sql.Identifier(target.database),
                sql.Identifier(target.migrator),
                sql.Identifier(target.app),
            ),
        )

    with target.connect(target.database) as database:
        if _schema(database) is None:
            _run(
                database,
                sql.SQL("CREATE SCHEMA app AUTHORIZATION {}").format(
                    sql.Identifier(target.owner)
                ),
            )
            print("已创建 schema: app")
        _run(database, "REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        _run(
            database,
            sql.SQL("GRANT USAGE ON SCHEMA app TO {}").format(sql.Identifier(target.app)),
        )
        if _table(database) is None:
            try:
                _run(database, sql.SQL("SET ROLE {}").format(sql.Identifier(target.owner)))
                _run(database, "CREATE TABLE app.connection_probe (id bigint PRIMARY KEY)")
                print("已创建测试表: app.connection_probe")
            finally:
                _run(database, "RESET ROLE")
        _check_table(database, target.owner)
        _run(
            database,
            sql.SQL("GRANT SELECT ON TABLE app.connection_probe TO {}").format(
                sql.Identifier(target.app)
            ),
        )
        _verify_privileges(database, target)
    print(f"完成: {target.database}.app.connection_probe")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="首次初始化 SelfLore PostgreSQL 环境")
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    parser.add_argument("--host", required=True, help="主机或 Unix socket 目录")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--admin-user", required=True)
    parser.add_argument(
        "--prompt-admin-password", action="store_true", help="隐藏输入管理员密码"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port 必须在 1 到 65535 之间")
    if args.prompt_admin_password and not sys.stdin.isatty():
        parser.error("--prompt-admin-password 需要交互终端")
    admin_password = getpass.getpass("管理员密码: ") if args.prompt_admin_password else None
    target = Target(args.env, args.host, args.port, args.admin_user, admin_password)
    try:
        bootstrap(target)
    except BootstrapError as exc:
        print(f"初始化失败: {exc}", file=sys.stderr)
        return 1
    except psycopg.OperationalError:
        print("数据库连接失败，请核对主机、端口、管理员角色和认证方式", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        print(f"数据库操作失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
