"""Apply immutable SQL migrations and version-specific grants to one database."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import psycopg
from psycopg import sql

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_LOCK = 436177100223001
GRANTS = {
    "0001_identity": {
        "users": "SELECT, INSERT, UPDATE", "auth_sessions": "SELECT, INSERT, UPDATE",
        "auth_login_throttle": "SELECT, INSERT, UPDATE, DELETE", "account_audit": "INSERT",
    },
    "0002_card_workspace": {
        **{name: "SELECT, INSERT, UPDATE" for name in ("user_profiles", "cards", "collections")},
        **{name: "SELECT, INSERT, UPDATE, DELETE" for name in
           ("topics", "tags", "card_topics", "card_tags", "card_links", "collection_items")},
        "activity_events": "SELECT, INSERT",
    },
    "0003_knowledge_review": {
        "review_units": "SELECT, INSERT, UPDATE", "review_states": "SELECT, INSERT, UPDATE",
        "review_logs": "SELECT, INSERT",
    },
}

class MigrationError(Exception):
    pass

def _identity(environment: str) -> tuple[str, str, str, str]:
    if environment not in {"dev", "prod"}:
        raise MigrationError("环境只能是 dev 或 prod")
    stem = f"selflore_{environment}"
    return stem, f"{stem}_migrator", f"{stem}_owner", f"{stem}_app"

def _files(directory: Path) -> list[Path]:
    files = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not files or len({item.stem[:4] for item in files}) != len(files):
        raise MigrationError("迁移文件缺失或版本号重复")
    return files

def migrate(environment: str, host: str, port: int, directory: Path = MIGRATIONS_DIR) -> list[str]:
    database, migrator, owner, app_role = _identity(environment)
    files = _files(directory)
    payloads = {p.stem: p.read_bytes() for p in files}
    checksums = {key: hashlib.sha256(value).hexdigest() for key, value in payloads.items()}
    options = dict(dbname=database, user=migrator, host=host, port=port, connect_timeout=5, autocommit=True)
    if os.environ.get("SELFLORE_MIGRATOR_PASSWORD"):
        options["password"] = os.environ["SELFLORE_MIGRATOR_PASSWORD"]
    completed: list[str] = []
    with psycopg.connect(**options) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, current_setting('server_version_num')::integer")
            actual_db, actual_user, version = cursor.fetchone()
            if (actual_db, actual_user, version // 10000) != (database, migrator, 18):
                raise MigrationError("目标数据库、迁移角色或 PostgreSQL 版本与预期不符")
            cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        try:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(owner)))
                cursor.execute("SELECT to_regclass('app.schema_migrations')")
                history = {}
                if cursor.fetchone()[0] is not None:
                    cursor.execute("SELECT version, checksum_sha256 FROM app.schema_migrations ORDER BY version")
                    history = dict(cursor.fetchall())
                for key, checksum in history.items():
                    if key not in checksums:
                        raise MigrationError("数据库存在本地缺失的历史迁移文件")
                    if checksum != checksums[key]:
                        raise MigrationError(f"已执行的迁移被改动: {key}.sql")
                if list(history) != list(payloads)[:len(history)]:
                    raise MigrationError("迁移历史不是本地版本链的连续前缀")
                if not history and files[0].stem != "0001_identity":
                    raise MigrationError("迁移历史表缺失，必须从首个版本开始")
            for key, content in payloads.items():
                if key in history:
                    continue
                with connection.transaction(), connection.cursor() as cursor:
                    cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(owner)))
                    cursor.execute(content.decode("utf-8"))
                    for table, privileges in GRANTS.get(key, {}).items():
                        cursor.execute(sql.SQL("GRANT {} ON TABLE app.{} TO {}").format(
                            sql.SQL(privileges), sql.Identifier(table), sql.Identifier(app_role)))
                    cursor.execute("INSERT INTO app.schema_migrations(version,checksum_sha256) VALUES (%s,%s)",
                                   (key, checksums[key]))
                completed.append(key)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
    return completed

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="对指定 SelfLore 环境执行版本迁移")
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port 必须在 1 到 65535 之间")
    try:
        versions = migrate(args.env, args.host, args.port)
    except (MigrationError, psycopg.Error, UnicodeError) as exc:
        print(f"迁移失败: {exc.__class__.__name__}: {exc}")
        return 1
    print("已执行版本: " + (", ".join(versions) if versions else "无（已是最新）"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
