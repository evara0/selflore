"""Destructive schema rehearsal only in the workspace-owned disposable 6179 cluster."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import os
import psycopg
import pytest
from app.db_bootstrap import Target,bootstrap
from app.db_migrate import GRANTS,MIGRATIONS_DIR,MigrationError,migrate
from test_auth_integration import isolated_database

DSN='host=127.0.0.1 port=6179 dbname=selflore_prod user=selflore_prod_migrator'


def reset_disposable_prod():
    assert os.environ['SELFLORE_TEST_ISOLATED']=='1'
    with psycopg.connect('host=127.0.0.1 port=6179 dbname=postgres user=postgres') as db:
        data=Path(db.execute("SHOW data_directory").fetchone()[0]).resolve()
        allowed=Path(__file__).resolve().parents[3]/'.cache'/'card-tests'
        assert data.is_relative_to(allowed.resolve()),'Never reset an external cluster'
    with psycopg.connect(DSN) as db:
        assert db.execute('SELECT inet_server_port(),current_database()').fetchone()==(6179,'selflore_prod')
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        db.execute('DROP SCHEMA app CASCADE')
        db.execute('CREATE SCHEMA app AUTHORIZATION selflore_prod_owner')
        db.execute('GRANT USAGE ON SCHEMA app TO selflore_prod_app')


def signature(dsn,environment):
    with psycopg.connect(dsn) as db:
        db.execute('SET LOCAL ROLE selflore_'+environment+'_owner')
        queries=[
            "SELECT table_name,column_name,ordinal_position,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='app' AND table_name<>'connection_probe' ORDER BY 1,3",
            "SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='app' AND c.relname<>'connection_probe' ORDER BY 1,2",
            "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='app' AND tablename<>'connection_probe' ORDER BY 1,2",
            "SELECT table_name,grantee,privilege_type FROM information_schema.role_table_grants WHERE table_schema='app' AND table_name<>'connection_probe' ORDER BY 1,2,3",
        ]
        return [repr(db.execute(q).fetchall()).replace('selflore_'+environment,'selflore_ENV') for q in queries]


def test_empty_and_existing_baselines_concurrency_and_grant_rollback(tmp_path,monkeypatch):
    # The role names mirror production, but the target is exclusively the disposable local cluster.
    monkeypatch.setenv('SELFLORE_MIGRATOR_PASSWORD',str(uuid4()))
    monkeypatch.setenv('SELFLORE_APP_PASSWORD',str(uuid4()))
    bootstrap(Target('prod','127.0.0.1',6179,'postgres'))
    reset_disposable_prod()
    assert migrate('prod','127.0.0.1',6179)==['0001_identity','0002_card_workspace','0003_knowledge_review']
    empty=signature(DSN,'prod')
    assert empty==signature(os.environ['SELFLORE_TEST_MIGRATOR_DSN'],'dev')
    assert migrate('prod','127.0.0.1',6179)==[]
    reset_disposable_prod()
    baseline=tmp_path/'baseline'; baseline.mkdir()
    (baseline/'0001_identity.sql').write_bytes((MIGRATIONS_DIR/'0001_identity.sql').read_bytes())
    assert migrate('prod','127.0.0.1',6179,baseline)==['0001_identity']
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        owner=uuid4()
        db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'existing','unchanged-hash')",(owner,))
        db.execute("INSERT INTO app.auth_sessions(id,user_id,token_hash,csrf_token,expires_at) VALUES(%s,%s,%s,'existing-token',now()+interval '1 day')",(uuid4(),owner,b'x'*32))
        users=db.execute('SELECT * FROM app.users ORDER BY id').fetchall()
        sessions=db.execute('SELECT * FROM app.auth_sessions ORDER BY id').fetchall()
    with ThreadPoolExecutor(max_workers=2) as pool:
        completed=list(pool.map(lambda _:migrate('prod','127.0.0.1',6179),range(2)))
    assert sorted(map(len,completed))==[0,2]
    assert signature(DSN,'prod')==empty
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert db.execute('SELECT * FROM app.users ORDER BY id').fetchall()==users
        assert db.execute('SELECT * FROM app.auth_sessions ORDER BY id').fetchall()==sessions
        assert db.execute('SELECT display_name FROM app.user_profiles WHERE user_id=%s',(owner,)).fetchone()==('existing',)
        assert db.execute('SELECT count(*) FROM app.cards').fetchone()==(0,)
    fault=tmp_path/'grant-failure'; fault.mkdir()
    for file in MIGRATIONS_DIR.glob('*.sql'): (fault/file.name).write_bytes(file.read_bytes())
    (fault/'0004_grant_failure.sql').write_text('CREATE TABLE app.must_rollback(id int);',encoding='utf-8')
    monkeypatch.setitem(GRANTS,'0004_grant_failure',{'missing_table':'SELECT'})
    with pytest.raises(psycopg.errors.UndefinedTable): migrate('prod','127.0.0.1',6179,fault)
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert db.execute("SELECT to_regclass('app.must_rollback')").fetchone()==(None,)
        assert db.execute("SELECT count(*) FROM app.schema_migrations WHERE version='0004_grant_failure'").fetchone()==(0,)
    (fault/'0002_card_workspace.sql').write_bytes((MIGRATIONS_DIR/'0002_card_workspace.sql').read_bytes()+b'\n-- changed')
    with pytest.raises(MigrationError,match='改动'): migrate('prod','127.0.0.1',6179,fault)
