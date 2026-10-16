"""Consistent dev backup and password-protected, new-cluster restore rehearsal."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import time
from uuid import uuid4

import psycopg
from psycopg import sql

from app.local_start import PROJECT_DIR, LocalConfigurationError, protect_directory
from app.media_storage import MediaConfig, MediaError, MARKER,load_media_environment
from app.media_backup import pack_media,validate_media,restore_media

BACKUPS = PROJECT_DIR / 'backups' / 'database'
REHEARSALS = PROJECT_DIR / '.cache' / 'restore-rehearsals'
HOST, SOURCE_PORT, RESTORE_PORT = '127.0.0.1', 6171, 6179
SOURCE_DB, MIGRATOR, OWNER, APP = 'selflore_dev', 'selflore_dev_migrator', 'selflore_dev_owner', 'selflore_dev_app'


class BackupError(Exception):
    pass


def stamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def environment(password: str) -> dict[str, str]:
    values = dict(os.environ)
    for key in list(values):
        if key.startswith('PG') or key == 'SELFLORE_MIGRATOR_PASSWORD':
            values.pop(key, None)
    values['PGPASSWORD'] = password
    return values


def tools() -> Path:
    configured = os.environ.get('SELFLORE_PG_BIN')
    located = shutil.which('pg_dump')
    candidates = [Path(configured)] if configured else ([Path(located).parent] if located else [])
    candidates += [Path('D:/Program Files/PostgreSQL/pgsql/bin'), Path('C:/Program Files/PostgreSQL/18/bin')]
    for directory in candidates:
        if all((directory / (name + ('.exe' if os.name == 'nt' else ''))).is_file() for name in ('pg_dump', 'pg_restore', 'initdb', 'pg_ctl')):
            executable = directory / ('pg_dump.exe' if os.name == 'nt' else 'pg_dump')
            result = subprocess.run([str(executable), '--version'], capture_output=True, text=True, check=True)
            if not re.search(r'PostgreSQL\) 18\.', result.stdout):
                raise BackupError('备份恢复工具必须是PostgreSQL 18。')
            return directory
    raise BackupError('未找到完整PG18工具，请配置SELFLORE_PG_BIN为bin目录。')


def run_tool(bin_dir: Path, name: str, args: list[str], password: str, log: Path) -> None:
    executable = bin_dir / (name + ('.exe' if os.name == 'nt' else ''))
    with log.open('ab') as output:
        result = subprocess.run([str(executable), *args], env=environment(password), stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise BackupError(f'{name}未成功；详情仅保存在私有日志：{log}')


def signature(connection) -> dict:
    connection.execute("SET LOCAL TIME ZONE 'UTC'")
    connection.execute('SET LOCAL search_path=pg_catalog')
    tables = connection.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') AND schemaname NOT LIKE 'pg_toast%' ORDER BY 1,2").fetchall()
    data = {}
    for schema, table in tables:
        digest = hashlib.sha256(); count = 0
        with connection.cursor(name='fingerprint_' + uuid4().hex) as cursor:
            cursor.execute(sql.SQL('SELECT row_to_json(t)::text FROM {}.{} t ORDER BY row_to_json(t)::text').format(sql.Identifier(schema), sql.Identifier(table)))
            for row in cursor:
                digest.update(row[0].encode('utf-8')); digest.update(b'\n'); count += 1
        data[f'{schema}.{table}'] = {'rows': count, 'sha256': digest.hexdigest()}
    queries = {
        'columns': "SELECT table_schema,table_name,column_name,ordinal_position,data_type,udt_schema,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,4",
        'constraints': "SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3",
        'indexes': "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3",
        'owners': "SELECT schemaname,tablename,tableowner FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2",
        'table_grants': "SELECT n.nspname,c.relname,pg_get_userbyid(a.grantor),CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,a.privilege_type,a.is_grantable FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND c.relkind IN ('r','p') ORDER BY 1,2,3,4,5,6",
        'schemas': "SELECT n.nspname,pg_get_userbyid(n.nspowner),pg_get_userbyid(a.grantor),CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,a.privilege_type,a.is_grantable FROM pg_namespace n CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_%' ORDER BY 1,2,3,4,5,6",
        'extensions': "SELECT e.extname,e.extversion,n.nspname,pg_get_userbyid(e.extowner) FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace ORDER BY 1",
        'history': 'SELECT version,checksum_sha256 FROM app.schema_migrations ORDER BY version',
    }
    structure = {key: [list(row) for row in connection.execute(query).fetchall()] for key, query in queries.items()}
    return {'tables': data, 'structure': structure}


def comparable_signature(value: dict) -> dict:
    """Only canonicalize the two exact PG18 representations of migration 0004's check.

    pg_dump/reparse flattens associative AND nodes. Do not strip arbitrary parentheses
    or normalize unrelated constraints: changed bounds, regex, owners or ACL still fail.
    """
    lower='(char_length((username)::text) >= 3)'
    upper='(char_length((username)::text) <= 32)'
    pattern='(((username)::text COLLATE "C") !~ \'[^a-z0-9_一-鿿-]\'::text)'
    nested=f'CHECK ((({lower} AND {upper}) AND {pattern}))'
    flat=f'CHECK (({lower} AND {upper} AND {pattern}))'
    result={**value,'structure':{**value['structure']}}
    if 'constraints' in value['structure']:
        result['structure']['constraints']=[
            [*row[:3],flat] if row[:3]==['app','users','users_username_check'] and row[3] in (nested,flat) else row
            for row in value['structure']['constraints']]
    return result


def backup(bin_dir: Path) -> Path:
    started=time.monotonic()
    load_media_environment(PROJECT_DIR/'apps/api/.env')
    if os.environ.get('SELFLORE_ENV','dev')!='dev':
        raise BackupError('本机固定备份仅允许开发库')
    password = os.environ.get('SELFLORE_MIGRATOR_PASSWORD')
    if not password:
        raise BackupError('缺少迁移角色凭据，请通过本机用户环境配置；不要写入参数或聊天。')
    protect_directory(BACKUPS)
    bundle = BACKUPS / ('dev-' + stamp()); bundle.mkdir()
    dump = bundle / 'selflore_dev.dump'
    with psycopg.connect(host=HOST, hostaddr=HOST, port=SOURCE_PORT, dbname=SOURCE_DB, user=MIGRATOR, password=password, connect_timeout=5) as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        actual = connection.execute("SELECT current_database(),current_user,inet_server_port(),current_setting('server_version_num')::integer").fetchone()
        if actual[:3] != (SOURCE_DB, MIGRATOR, SOURCE_PORT) or actual[3] // 10000 != 18:
            raise BackupError('源库身份、端口或PG版本不符，拒绝备份。')
        connection.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
        exported = connection.execute('SELECT pg_export_snapshot()').fetchone()[0]
        baseline = signature(connection)
        media=[]
        if 'app.attachments' in baseline['tables']:
            from psycopg.rows import dict_row
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT id,owner_id,original_key,thumbnail_key,original_bytes,thumbnail_bytes,original_sha256,thumbnail_sha256 FROM app.attachments WHERE status='ready' ORDER BY id")
                media=[{k:str(v) if k in ('id','owner_id') else v for k,v in row.items()} for row in cursor.fetchall()]
            pack_media(MediaConfig.load(),media,bundle)
        run_tool(bin_dir, 'pg_dump', ['--host='+HOST, '--port='+str(SOURCE_PORT), '--username='+MIGRATOR, '--dbname='+SOURCE_DB, '--role='+OWNER, '--no-password', '--format=custom', '--snapshot='+exported, '--file='+str(dump)], password, bundle / 'backup.log')
    run_tool(bin_dir, 'pg_restore', ['--list', str(dump)], '', bundle / 'archive.list')
    if not dump.stat().st_size:
        raise BackupError('备份文件为空，未创建完成清单。')
    manifest = {'format': 'selflore-backup-v1', 'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'source': {'host': HOST, 'port': SOURCE_PORT, 'database': SOURCE_DB, 'role': MIGRATOR, 'pg_major': 18}, 'snapshot_consistent': True, 'dump_sha256': file_hash(dump), 'signature': baseline}
    if 'app.attachments' in baseline['tables']:
        manifest.update(format='selflore-backup-v2',media=media,completed_at=datetime.now(timezone.utc).isoformat(),duration_seconds=time.monotonic()-started,
                        media_bytes=sum(item['original_bytes']+item['thumbnail_bytes'] for item in media))
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'开发库完整备份已生成：{bundle}', flush=True)
    return bundle


def validate_bundle(bundle: Path) -> dict:
    bundle = bundle.resolve()
    if not bundle.is_relative_to(BACKUPS.resolve()) or bundle == BACKUPS.resolve():
        raise BackupError('只允许演练本项目私有备份目录中的完整备份包。')
    try:
        manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise BackupError('备份清单格式无效。')
        if manifest.get('format') not in ('selflore-backup-v1','selflore-backup-v2') or manifest.get('source') != {'host': HOST, 'port': SOURCE_PORT, 'database': SOURCE_DB, 'role': MIGRATOR, 'pg_major': 18} or not manifest.get('snapshot_consistent'):
            raise BackupError('备份格式或源身份不符。')
        if file_hash(bundle / 'selflore_dev.dump') != manifest['dump_sha256']:
            raise BackupError('备份文件校验和不符，拒绝恢复。')
        if not isinstance(manifest.get('signature'), dict) or not manifest['signature'].get('tables') or not isinstance(manifest['signature'].get('structure'), dict) or not manifest['signature']['structure'].get('history'):
            raise BackupError('备份核验清单不完整。')
        if manifest['format']=='selflore-backup-v1' and 'app.attachments' in manifest['signature']['tables']:
            raise BackupError('含附件结构的新库不能使用数据库-only旧备份')
        if manifest['format']=='selflore-backup-v2':
            if not isinstance(manifest.get('media'),list) or 'app.attachments' not in manifest['signature']['tables']:
                raise BackupError('联合备份附件清单不完整')
            if manifest['media']: validate_media(bundle/'media',manifest['media'])
        return manifest
    except (OSError, ValueError, KeyError, TypeError, MediaError):
        raise BackupError('备份包缺失或清单损坏，拒绝恢复。') from None


def check_restore_port() -> None:
    try:
        with socket.socket() as listener:
            listener.bind((HOST, RESTORE_PORT))
    except OSError:
        raise BackupError('6179端口被占用；请结束已有测试服务后重试，不会停止其他实例。') from None


def verify_app(database: str, password: str) -> dict:
    with psycopg.connect(host=HOST, hostaddr=HOST, port=RESTORE_PORT, dbname=database, user=APP, password=password, connect_timeout=5) as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        if connection.execute('SELECT current_user,current_database(),inet_server_port()').fetchone() != (APP, database, RESTORE_PORT):
            raise BackupError('恢复应用读取身份不符。')
        counts = {}
        for table in ('users','auth_sessions','user_profiles','cards','card_links','memo_items','memo_item_links','collections','collection_items','review_units','review_states','review_logs'):
            if table in ('memo_items','memo_item_links') and connection.execute('SELECT to_regclass(%s)',('app.'+table,)).fetchone()[0] is None:
                continue  # Restoring an older backup must not require a later migration.
            counts[table] = connection.execute(sql.SQL('SELECT count(*) FROM app.{}').format(sql.Identifier(table))).fetchone()[0]
        restricted = connection.execute("SELECT has_schema_privilege(current_user,'app','CREATE'),has_table_privilege(current_user,'app.cards','TRUNCATE'),has_table_privilege(current_user,'app.schema_migrations','SELECT'),has_table_privilege(current_user,'app.review_logs','UPDATE')").fetchone()
        if restricted != (False,False,False,False):
            raise BackupError('恢复应用角色权限超出预期。')
        return counts


def rehearse(bundle: Path, bin_dir: Path) -> Path:
    started=time.monotonic(); restore_started_at=datetime.now(timezone.utc).isoformat()
    manifest = validate_bundle(bundle)
    check_restore_port()
    protect_directory(REHEARSALS)
    folder = REHEARSALS / ('restore-' + stamp()); folder.mkdir()
    if manifest['format']=='selflore-backup-v1':
        # Inspect the actual dump, not just a user-editable manifest.
        run_tool(bin_dir,'pg_restore',['--list',str(bundle/'selflore_dev.dump')],'',folder/'legacy-archive.list')
        if ' app attachments ' in (folder/'legacy-archive.list').read_text(encoding='utf-8'):
            raise BackupError('旧格式dump包含附件结构，拒绝数据库-only恢复')
    data = folder / 'pgdata'; database = 'selflore_restore_' + uuid4().hex[:12]
    admin_password, app_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    pwfile = folder / 'initdb-password'; pwfile.write_text(admin_password, encoding='utf-8')
    start_attempted = False
    result = None
    try:
        run_tool(bin_dir, 'initdb', ['-D',str(data),'-U','postgres','--pwfile='+str(pwfile),'--auth-host=scram-sha-256','--auth-local=scram-sha-256','-E','UTF8'], '', folder / 'initdb.log')
        pwfile.unlink()
        start_attempted = True
        run_tool(bin_dir, 'pg_ctl', ['start','-D',str(data),'-l',str(folder/'postgres.log'),'-o',f'-p {RESTORE_PORT} -h {HOST}','-w','-t','20'], '', folder / 'control.log')
        admin = dict(host=HOST,hostaddr=HOST,port=RESTORE_PORT,dbname='postgres',user='postgres',password=admin_password,connect_timeout=5,autocommit=True)
        with psycopg.connect(**admin) as connection:
            actual_dir = Path(connection.execute('SHOW data_directory').fetchone()[0]).resolve()
            actual = connection.execute("SELECT inet_server_port(),current_setting('server_version_num')::integer").fetchone()
            if actual_dir != data.resolve() or actual[0] != RESTORE_PORT or actual[1] // 10000 != 18:
                raise BackupError('隔离实例实际目录、端口或版本不符。')
            connection.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(OWNER)))
            for role in (APP,MIGRATOR):
                connection.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role),sql.Literal(app_password)))
            connection.execute(sql.SQL('GRANT {} TO {} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE').format(sql.Identifier(OWNER),sql.Identifier(MIGRATOR)))
            connection.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0').format(sql.Identifier(database),sql.Identifier(OWNER)))
            connection.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(database)))
            connection.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {},{}').format(sql.Identifier(database),sql.Identifier(APP),sql.Identifier(MIGRATOR)))
        run_tool(bin_dir, 'pg_restore', ['--host='+HOST,'--port='+str(RESTORE_PORT),'--username=postgres','--dbname='+database,'--role='+OWNER,'--no-password','--exit-on-error','--single-transaction',str(bundle/'selflore_dev.dump')], admin_password, folder / 'restore.log')
        with psycopg.connect(**{**admin,'dbname':database,'autocommit':False}) as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            connection.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
            restored = signature(connection)
        if comparable_signature(restored) != comparable_signature(manifest['signature']):
            mismatches = [key for key in ('tables','structure') if restored.get(key) != manifest['signature'].get(key)]
            (folder/'restored-signature.json').write_text(json.dumps(restored,ensure_ascii=False,indent=2),encoding='utf-8')
            raise BackupError('恢复核验不一致：'+', '.join(mismatches)+'；核对结果仅保存在私有演练目录。')
        counts = verify_app(database, app_password)
        media_verified=False
        if manifest['format']=='selflore-backup-v2':
            restored_media=folder/'media'; restore_media(bundle,manifest['media'],restored_media)
            ops=folder/'ops'; protect_directory(ops)
            for root,kind in ((restored_media,'media'),(ops,'ops')):
                (root/MARKER).write_text(json.dumps({'environment':'dev','database':'selflore_dev','kind':kind}),encoding='utf-8')
            verify_media_http(admin,database,app_password,restored_media,ops,manifest['media'])
            media_verified=True
        result = {'status':'passed','source':manifest['source'],'backup_bundle':str(bundle),'backup_sha256':manifest['dump_sha256'],'target':{'host':HOST,'port':RESTORE_PORT,'database':database,'data_directory':str(data)},'table_count':len(restored['tables']),'data_structure_permissions_history_equal':True,'app_read_counts':counts,'business_data_empty':counts['cards']==0,'cluster_stopped':True}
        result.update(media_verified=media_verified,restore_started_at=restore_started_at,restore_completed_at=datetime.now(timezone.utc).isoformat(),duration_seconds=time.monotonic()-started)
    finally:
        if pwfile.exists(): pwfile.unlink()
        if start_attempted:
            run_tool(bin_dir,'pg_ctl',['stop','-D',str(data),'-m','fast','-w','-t','20'],'',folder/'control.log')
    (folder/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'隔离恢复演练通过：{len(manifest["signature"]["tables"])}张表数据、结构、权限和迁移历史一致；实例已停止。',flush=True)
    print(f'私有验收记录：{folder / "verification.json"}',flush=True)
    return folder


def verify_media_http(admin,database,password,media_root,ops_root,entries):
    """Ephemeral sessions only in the freshly restored private database, removed after probes."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.auth import get_db
    from app.main import create_app
    from app.media_storage import file_hash
    with patch.dict(os.environ,{'SELFLORE_ENV':'dev','SELFLORE_MEDIA_ROOT':str(media_root),'SELFLORE_MEDIA_OPS_ROOT':str(ops_root)}):
        app=create_app()
        def restored_connection():
            with psycopg.connect(host=HOST,port=RESTORE_PORT,dbname=database,user=APP,password=password) as db:
                db.execute('SET TRANSACTION READ ONLY'); yield db
        app.dependency_overrides[get_db]=restored_connection
        for entry in entries:
            session_id=uuid4(); raw=secrets.token_urlsafe(32)
            with psycopg.connect(**{**admin,'dbname':database}) as db:
                active=db.execute('SELECT is_active FROM app.users WHERE id=%s',(entry['owner_id'],)).fetchone()[0]
                db.execute('INSERT INTO app.auth_sessions(id,user_id,token_hash,csrf_token,expires_at) VALUES(%s,%s,%s,%s,now()+interval \'10 minutes\')',
                           (session_id,entry['owner_id'],hashlib.sha256(raw.encode()).digest(),'restore-probe'))
            try:
                with TestClient(app) as http:
                    http.cookies.set('selflore_session_dev',raw)
                    for variant in ('original','thumbnail'):
                        response=http.get(f"/api/attachments/{entry['id']}/content?variant={variant}")
                        if not active:
                            if response.status_code!=401: raise BackupError('停用用户图片读取权限核验失败')
                        elif response.status_code!=200 or hashlib.sha256(response.content).hexdigest()!=entry[variant+'_sha256']:
                            raise BackupError('恢复后本人图片鉴权读取核验失败')
            finally:
                with psycopg.connect(**{**admin,'dbname':database}) as db:
                    db.execute('DELETE FROM app.auth_sessions WHERE id=%s',(session_id,))


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description='SelfLore开发库备份与隔离恢复演练')
    parser.add_argument('--rehearse',action='store_true')
    parser.add_argument('--bundle',type=Path)
    args=parser.parse_args(argv)
    if args.bundle and not args.rehearse: parser.error('--bundle需要--rehearse')
    try:
        bin_dir=tools()
        bundle=args.bundle.resolve() if args.bundle else backup(bin_dir)
        if args.rehearse: rehearse(bundle,bin_dir)
        return 0
    except (BackupError,LocalConfigurationError,MediaError) as error:
        print(f'备份/演练未完成：{error}'); return 1
    except (psycopg.Error,OSError,subprocess.CalledProcessError):
        print('备份/演练未完成：连接、工具或文件权限错误；未输出凭据或原始数据。'); return 1


if __name__=='__main__':
    raise SystemExit(main())
