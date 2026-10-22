import os
import json
import time
import subprocess
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from app.db_bootstrap import Target, bootstrap
from app.db_migrate import MIGRATIONS_DIR, GRANTS, migrate
from app.services.cards import digest, create_card
from app.schemas.workspace import CardCreate
from app.tag_preflight import report
from test_auth_integration import isolated_database
from test_card_migration_rehearsal import reset_disposable_prod, DSN


def baseline(tmp_path,monkeypatch):
    monkeypatch.setenv('SELFLORE_MIGRATOR_PASSWORD',str(uuid4()))
    monkeypatch.setenv('SELFLORE_APP_PASSWORD',str(uuid4()))
    bootstrap(Target('prod','127.0.0.1',6179,'postgres')); reset_disposable_prod()
    folder=tmp_path/'baseline'; folder.mkdir()
    for f in MIGRATIONS_DIR.glob('*.sql'):
        if int(f.name[:4])<=6: (folder/f.name).write_bytes(f.read_bytes())
    migrate('prod','127.0.0.1',6179,folder)


def test_upgrade_dedup_provenance_retries_backup_restore(tmp_path,monkeypatch):
    baseline(tmp_path,monkeypatch)
    owner,other=uuid4(),uuid4()
    common=uuid4(); topic_ids=[]
    data=CardCreate(kind='opinion',title='原观点',body_md='原文',client_request_id=uuid4())
    card=uuid4()
    with psycopg.connect(DSN,row_factory=dict_row) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        for actor,name in [(owner,'legacy'),(other,'other')]:
            db.execute('INSERT INTO app.users(id,username,password_hash) VALUES(%s,%s,%s)',(actor,name,'unchanged'))
        db.execute("INSERT INTO app.cards(id,owner_id,code,kind,title,body_md,search_text,client_request_id,creation_request_digest) VALUES(%s,%s,'old','opinion',%s,%s,'原文',%s,%s)",(card,owner,data.title,data.body_md,data.client_request_id,digest(data.model_dump(mode='json',exclude={'taxonomy_mode'}))))
        db.execute('INSERT INTO app.tags(id,owner_id,name) VALUES(%s,%s,%s)',(common,owner,'ＡＩ'))
        db.execute('INSERT INTO app.card_tags VALUES(%s,%s,%s)',(owner,card,common))
        for kind in ('knowledge','reference','opinion'):
            entity=uuid4(); topic_ids.append(entity)
            db.execute('INSERT INTO app.topics(id,owner_id,kind,name) VALUES(%s,%s,%s,%s)',(entity,owner,kind,'AI'))
            if kind=='opinion': db.execute("INSERT INTO app.card_topics VALUES(%s,%s,%s,'opinion')",(owner,card,entity))
        foreign=uuid4()
        db.execute("INSERT INTO app.topics(id,owner_id,kind,name) VALUES(%s,%s,'opinion','AI')",(foreign,other))
        # Same UUID in topics and tags must not identify two unrelated tags.
        collision=uuid4()
        db.execute("INSERT INTO app.tags(id,owner_id,name) VALUES(%s,%s,'不同标签')",(collision,owner))
        db.execute("INSERT INTO app.topics(id,owner_id,kind,name) VALUES(%s,%s,'opinion',%s)",(collision,owner,'长'*80))
        # Fill the original opinion with ten topics plus twenty tags (30 distinct after union).
        extra_topics=[]
        for n in range(9):
            t=uuid4();extra_topics.append(t);db.execute("INSERT INTO app.topics(id,owner_id,kind,name) VALUES(%s,%s,'opinion',%s)",(t,owner,'主题'+str(n)))
            db.execute("INSERT INTO app.card_topics VALUES(%s,%s,%s,'opinion')",(owner,card,t))
        for n in range(19):
            t=uuid4();db.execute('INSERT INTO app.tags(id,owner_id,name) VALUES(%s,%s,%s)',(t,owner,'标签'+str(n)))
            db.execute('INSERT INTO app.card_tags VALUES(%s,%s,%s)',(owner,card,t))
        maximum=uuid4()
        db.execute("INSERT INTO app.cards(id,owner_id,code,kind,title,body_md,search_text,client_request_id,creation_request_digest) VALUES(%s,%s,'maximum','opinion','最大关联','正文','正文',%s,%s)",(maximum,owner,uuid4(),'0'*64))
        db.execute('INSERT INTO app.card_tags SELECT owner_id,%s,tag_id FROM app.card_tags WHERE card_id=%s',(maximum,card))
        for t in [collision,*extra_topics]: db.execute("INSERT INTO app.card_topics VALUES(%s,%s,%s,'opinion')",(owner,maximum,t))
        # Preserve archived and trashed associations too.
        for lifecycle in ('archived','trashed'):
            c=uuid4()
            db.execute("INSERT INTO app.cards(id,owner_id,code,kind,title,body_md,search_text,client_request_id,creation_request_digest,lifecycle,trashed_at) VALUES(%s,%s,%s,'reference','旧资料','摘录','摘录',%s,%s,%s,CASE WHEN %s='trashed' THEN now() END)",(c,owner,str(c),uuid4(),'0'*64,lifecycle,lifecycle))
            db.execute('INSERT INTO app.card_tags VALUES(%s,%s,%s)',(owner,c,common))
        before=db.execute('SELECT * FROM app.cards ORDER BY id').fetchall()
        inventory=report(db)
        assert inventory['owners'][str(owner)]['merged_groups']==1
    from app.schema_capability import ready
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert not ready(db)
    migration_started=time.perf_counter()
    assert migrate('prod','127.0.0.1',6179)==['0007_unified_card_tags','0008_tabular_checklists']
    migration_seconds=time.perf_counter()-migration_started
    assert migrate('prod','127.0.0.1',6179)==[]
    with psycopg.connect(DSN,row_factory=dict_row) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert ready(db)
        assert before==[{k:v for k,v in row.items() if k not in ('memo_columns','memo_column_count')} for row in db.execute('SELECT * FROM app.cards ORDER BY id').fetchall()]
        assert db.execute('SELECT count(*) AS n FROM app.card_tags WHERE card_id=%s',(card,)).fetchone()['n']==29
        assert db.execute('SELECT count(*) AS n FROM app.card_tags WHERE card_id=%s',(maximum,)).fetchone()['n']==30
        aliases=db.execute("SELECT canonical_tag_id FROM app.tag_aliases WHERE owner_id=%s AND original_name IN ('AI','ＡＩ')",(owner,)).fetchall()
        assert {r['canonical_tag_id'] for r in aliases}=={common}
        assert db.execute('SELECT canonical_tag_id FROM app.tag_aliases WHERE owner_id=%s AND old_id=%s',(other,foreign)).fetchone()['canonical_tag_id']!=common
        assert db.execute("SELECT canonical_tag_id FROM app.tag_aliases WHERE owner_id=%s AND old_id=%s AND source_type='topic'",(owner,collision)).fetchone()['canonical_tag_id']!=collision
        assert create_card(db,owner,data)['id']==card
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute('SET LOCAL ROLE selflore_prod_app')
                db.execute("UPDATE app.topics SET name='forbidden'")
    # Dump/restore only databases in this task-owned disposable cluster.
    restore_started=time.perf_counter()
    binary=Path(os.environ['SELFLORE_PG_BIN']); dump=tmp_path/'tags.dump'
    subprocess.run([str(binary/'pg_dump.exe' if os.name=='nt' else binary/'pg_dump'),'-h','127.0.0.1','-p','6179','-U','postgres','-d','selflore_prod','-Fc','-f',str(dump)],check=True)
    restored='tags_restore_'+uuid4().hex[:8]
    with psycopg.connect('host=127.0.0.1 port=6179 dbname=postgres user=postgres',autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(restored)))
        try:
            subprocess.run([str(binary/('pg_restore.exe' if os.name=='nt' else 'pg_restore')),'-h','127.0.0.1','-p','6179','-U','postgres','-d',restored,str(dump)],check=True)
            with psycopg.connect(f'host=127.0.0.1 port=6179 dbname={restored} user=selflore_prod_app',row_factory=dict_row) as db:
                assert create_card(db,owner,data)['id']==card
                from app.services import tags
                assert tags.resolve(db,owner,topic_ids[0],'topic')['tag_id']==common
                assert len(tags.listing(db,other)['items'])==1
                added=tags.write(db,other,type('Body',(),{'name':'恢复后写入'})())
                assert added['id']
                repaired=tags.write(db,owner,type('Body',(),{'name':'AI核验后'})(),entity=common)
                assert repaired['id']==common
                assert tags.resolve(db,owner,topic_ids[0],'topic')['name']=='AI核验后'
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(restored)))
    evidence=Path(__file__).resolve().parents[3]/'.cache/card-tests/tag-migration-rehearsal.json'
    evidence.write_text(json.dumps({'status':'passed','migration_seconds':migration_seconds,'backup_restore_seconds':time.perf_counter()-restore_started,'preflight':inventory,'old_card_rows_preserved':len(before),'old_id_resolution':True,'two_owner_isolation':True,'restored_write_verified':True,'compatible_forward_fix_verified':True,'locks':'migration advisory lock and original taxonomy ACCESS EXCLUSIVE locks','backup_boundary':'disposable fixture snapshot; no concurrent business writers; no production restore'},default=str,ensure_ascii=False,indent=2),encoding='utf-8')


def test_invalid_normalization_and_grant_failure_rollback(tmp_path,monkeypatch):
    baseline(tmp_path,monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import create_app
    with monkeypatch.context() as patch:
        patch.setenv('SELFLORE_DATABASE_URL',DSN)
        with pytest.raises(RuntimeError,match='统一标签'):
            with TestClient(create_app()): pass
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner'); owner=uuid4()
        db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'legacy','hash')",(owner,))
        db.execute("INSERT INTO app.topics(id,owner_id,kind,name) VALUES(%s,%s,'opinion',%s)",(uuid4(),owner,'\t'))
    with pytest.raises(psycopg.errors.RaiseException): migrate('prod','127.0.0.1',6179)
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert db.execute("SELECT to_regclass('app.tag_aliases')").fetchone()==(None,)
        db.execute("UPDATE app.topics SET name='有效'")
    with monkeypatch.context() as patch:
        patch.setitem(GRANTS,'0007_unified_card_tags',{'missing_table':'SELECT'})
        with pytest.raises(psycopg.errors.UndefinedTable): migrate('prod','127.0.0.1',6179)
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert db.execute("SELECT to_regclass('app.tag_aliases')").fetchone()==(None,)
        assert db.execute("SELECT count(*) FROM app.schema_migrations WHERE version='0007_unified_card_tags'").fetchone()==(0,)
    assert migrate('prod','127.0.0.1',6179)==['0007_unified_card_tags','0008_tabular_checklists']
