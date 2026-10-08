"""Create the first administrator through a migrator-only local command."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from fastapi import HTTPException

from app.auth import hasher, normalize_username, validate_password
from app.db_migrate import _identity


def create_first_admin(environment: str, host: str, port: int, username: str, password: str) -> None:
    database, migrator, owner, _ = _identity(environment)
    normalized = normalize_username(username)
    validate_password(password)
    options = dict(dbname=database, user=migrator, host=host, port=port, connect_timeout=5)
    if os.environ.get("SELFLORE_MIGRATOR_PASSWORD"):
        options["password"] = os.environ["SELFLORE_MIGRATOR_PASSWORD"]
    with psycopg.connect(**options) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            if cursor.fetchone() != (database, migrator):
                raise RuntimeError("数据库或迁移角色不匹配")
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (436177100223002,))
            cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(owner)))
            cursor.execute("SELECT EXISTS (SELECT 1 FROM app.users WHERE role = 'admin')")
            if cursor.fetchone()[0]:
                raise RuntimeError("管理员已存在，不会重复创建")
            user_id = uuid4()
            cursor.execute(
                "INSERT INTO app.users (id, username, password_hash, role) VALUES (%s, %s, %s, 'admin')",
                (user_id, normalized, hasher.hash(password)),
            )
            cursor.execute(
                "INSERT INTO app.account_audit (id, target_user_id, action, role_after, is_active_after) VALUES (%s, %s, 'bootstrap', 'admin', true)",
                (uuid4(), user_id),
            )
            cursor.execute("SELECT to_regclass('app.user_profiles')")
            if cursor.fetchone()[0] is not None:
                cursor.execute("INSERT INTO app.user_profiles(user_id, display_name) VALUES (%s, %s)", (user_id, normalized))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="创建 SelfLore 首位管理员")
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--username", required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port 必须在 1 到 65535 之间")
    if not sys.stdin.isatty():
        parser.error("需要交互终端输入管理员密码")
    password = getpass.getpass("管理员密码: ")
    confirmation = getpass.getpass("再次输入管理员密码: ")
    if password != confirmation:
        print("两次密码不一致", file=sys.stderr)
        return 1
    try:
        create_first_admin(args.env, args.host, args.port, args.username, password)
    except (psycopg.Error, RuntimeError, ValueError, HTTPException) as exc:
        print(f"创建失败: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    print("首位管理员已创建")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
