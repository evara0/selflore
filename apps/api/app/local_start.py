"""Explicit local-only configuration and checked unified Web/API startup."""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from app.media_storage import MediaConfig,MediaError,initialize

API_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = API_DIR.parent.parent
PASSWORD_FILE = PROJECT_DIR / '.cache' / 'local' / 'pgpass.conf'
HOST, PORT, DATABASE, ROLE = '127.0.0.1', '6171', 'selflore_dev', 'selflore_dev_app'
WEB_PORT = 24566
TABLES = ('users', 'auth_sessions', 'auth_login_throttle', 'account_audit',
          'user_profiles', 'cards', 'tag_aliases', 'card_tag_sources', 'topics', 'card_topics', 'tags', 'card_tags',
          'card_links', 'collections', 'collection_items', 'activity_events',
          'review_units', 'review_states', 'review_logs', 'attachments', 'card_attachments')


class LocalConfigurationError(Exception):
    pass


def configuration() -> dict[str, str]:
    if os.environ.get('SELFLORE_ENV', 'dev') != 'dev':
        raise LocalConfigurationError('本地入口只允许开发环境。')
    value = os.environ.get('SELFLORE_DATABASE_URL', '')
    if not value:
        raise LocalConfigurationError('缺少数据库配置，请检查 apps/api/.env。')
    try:
        options = conninfo_to_dict(value)
    except psycopg.Error:
        raise LocalConfigurationError('数据库连接参数格式无效，请检查 .env；诊断不会输出连接串。') from None
    if any(options.get(key) != expected for key, expected in
           (('host', HOST), ('port', PORT), ('dbname', DATABASE), ('user', ROLE))):
        raise LocalConfigurationError('本地入口仅允许127.0.0.1:6171/selflore_dev和selflore_dev_app角色。')
    if options.get('service') or options.get('hostaddr') or options.get('password'):
        raise LocalConfigurationError('请使用模板中的直接连接参数，密码通过 -Configure 单独配置。')
    password_file = Path(os.environ.get('PGPASSFILE', ''))
    if not os.environ.get('PGPASSFILE'):
        raise LocalConfigurationError('缺少PGPASSFILE，请检查 apps/api/.env。')
    if not password_file.is_absolute():
        password_file = API_DIR / password_file
    if password_file.resolve() != PASSWORD_FILE.resolve():
        raise LocalConfigurationError('本地凭据路径与模板不符，请检查PGPASSFILE。')
    os.environ['PGPASSFILE'] = str(password_file.resolve())
    for key in ('SELFLORE_MIGRATOR_PASSWORD', 'PGPASSWORD', 'PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'):
        os.environ.pop(key, None)
    return options


def protect_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        directory.chmod(0o700)
        return
    # Build a fresh protected DACL before any password bytes are written.
    script = """$ErrorActionPreference='Stop'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach($identity in @($sid,[Security.Principal.SecurityIdentifier]::new('S-1-5-18'))){
 $rule=[Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
 $acl.AddAccessRule($rule)
}
[IO.Directory]::SetAccessControl($env:SELFLORE_LOCAL_CREDENTIAL_DIR,$acl)
"""
    try:
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                       env={**os.environ, 'SELFLORE_LOCAL_CREDENTIAL_DIR': str(directory)},
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (OSError, subprocess.CalledProcessError):
        raise LocalConfigurationError('无法限制本机凭据目录权限，未写入新密码。') from None


def save_password(password: str, confirmation: str) -> None:
    if not password or password != confirmation:
        raise LocalConfigurationError('密码为空或两次输入不一致，未修改已有凭据。')
    if any(character in password for character in '\r\n\0'):
        raise LocalConfigurationError('密码不能含换行或空字符，未修改已有凭据。')
    protect_directory(PASSWORD_FILE.parent)
    escaped = password.replace('\\', '\\\\').replace(':', '\\:')
    content = f'{HOST}:{PORT}:{DATABASE}:{ROLE}:{escaped}\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=PASSWORD_FILE.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        if os.name != 'nt':
            temporary.chmod(0o600)
        temporary.replace(PASSWORD_FILE)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def check_database(options: dict[str, str]) -> None:
    if not PASSWORD_FILE.is_file() or not PASSWORD_FILE.stat().st_size:
        raise LocalConfigurationError('尚未配置应用密码。请在项目根运行 .\\start-local.cmd -Configure。')
    try:
        with psycopg.connect(**options, connect_timeout=5) as connection, connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SELECT current_database(),current_user,current_setting('server_version_num')::integer")
            target = cursor.fetchone()
            if target is None or target[:2] != (DATABASE, ROLE) or target[2] // 10000 != 18:
                raise LocalConfigurationError('数据库实际身份或版本不符；本地入口要求开发库app角色和PostgreSQL 18。')
            cursor.execute('SELECT normalized_name FROM app.tags LIMIT 0')
            for table in TABLES:
                # account_audit intentionally grants INSERT only; inspect its existence without reading rows.
                if table == 'account_audit':
                    cursor.execute("SELECT to_regclass('app.account_audit')")
                    if cursor.fetchone()[0] is None:
                        raise LocalConfigurationError('账号审计表缺失，请按迁移说明单独处理。')
                else:
                    cursor.execute(sql.SQL('SELECT 1 FROM app.{} LIMIT 0').format(sql.Identifier(table)))
            cursor.execute("SELECT has_schema_privilege(current_user,'app','CREATE'),has_table_privilege(current_user,'app.cards','TRUNCATE')")
            if cursor.fetchone() != (False, False):
                raise LocalConfigurationError('应用角色权限超出预期，请检查数据库授权。')
    except psycopg.OperationalError:
        raise LocalConfigurationError('开发库连接失败：确认PostgreSQL已启动并监听6171；若密码有误，重新运行 -Configure。') from None
    except psycopg.Error:
        raise LocalConfigurationError('开发库表或权限检查失败，请按数据库迁移说明单独核对；启动不会自动迁移。') from None


def check_port() -> None:
    try:
        with socket.socket() as listener:
            listener.bind((HOST, WEB_PORT))
    except OSError:
        raise LocalConfigurationError('24566端口已被占用，请先停止现有SelfLore服务再启动。') from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='SelfLore本机固定配置与启动')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--configure', action='store_true', help='隐藏输入并保存应用数据库密码')
    mode.add_argument('--check', action='store_true', help='只读检查配置、开发库和端口')
    mode.add_argument('--configure-media', action='store_true', help='显式初始化媒体和运维目录')
    parser.add_argument('--media-root',type=Path)
    parser.add_argument('--ops-root',type=Path)
    args = parser.parse_args(argv)
    try:
        options = configuration()
        media=MediaConfig.load()
        if args.configure_media:
            media.root=args.media_root or media.root
            media.ops_root=args.ops_root or media.ops_root
            initialize(media)
            print('媒体和运维目录已初始化；请将相同绝对路径写入SELFLORE_MEDIA_ROOT及SELFLORE_MEDIA_OPS_ROOT配置。')
            return 0
        if args.configure:
            if not sys.stdin.isatty():
                raise LocalConfigurationError('密码配置需要交互终端，请在本机PowerShell运行 .\\start-local.cmd -Configure。')
            password = getpass.getpass('请输入 selflore_dev_app 的既有数据库密码：')
            confirmation = getpass.getpass('再次输入确认：')
            save_password(password, confirmation)
            print('应用密码已保存到本机凭据文件；随后运行 .\\start-local.cmd -CheckOnly 核对。')
            return 0
        check_database(options)
        if media.root is not None:
            media.check(); media.check(ops=True)
            if not all(os.access(root,os.R_OK|os.W_OK) for root in (media.root,media.ops_root)):
                raise LocalConfigurationError('媒体或运维目录没有当前进程读写权限')
        check_port()
        print('本地配置检查通过：开发库app角色、PostgreSQL 18、业务表和24566端口。', flush=True)
        if args.check:
            return 0
        if not (PROJECT_DIR / 'apps/web/dist/index.html').is_file():
            raise LocalConfigurationError('前端尚未构建，请从项目根使用 start-local.cmd。')
        import uvicorn
        print('打开 http://127.0.0.1:24566，按Ctrl+C停止。', flush=True)
        uvicorn.run('app.main:app', host=HOST, port=WEB_PORT)
        return 0
    except LocalConfigurationError as error:
        print(f'启动配置未就绪：{error}')
        return 1
    except MediaError as error:
        print(f'媒体配置未就绪：{error}'); return 1
    except (EOFError, KeyboardInterrupt):
        print('已取消。')
        return 1
    except OSError:
        print('本机配置文件访问失败，请核对目录权限；未输出凭据。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
