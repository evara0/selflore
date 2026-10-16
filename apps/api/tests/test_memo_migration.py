from datetime import datetime, timezone
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from app.db_migrate import MIGRATIONS_DIR, migrate
from app.db_bootstrap import Target, bootstrap
from app.services.scheduling import fresh, VERSION
from test_auth_integration import isolated_database
from test_card_migration_rehearsal import reset_disposable_prod, DSN


def test_0005_to_memo_preserves_all_existing_tables_and_media_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv('SELFLORE_MIGRATOR_PASSWORD',str(uuid4()))
    monkeypatch.setenv('SELFLORE_APP_PASSWORD',str(uuid4()))
    bootstrap(Target('prod','127.0.0.1',6179,'postgres')); reset_disposable_prod()
    baseline=tmp_path/'0005'; baseline.mkdir()
    for path in MIGRATIONS_DIR.glob('*.sql'):
        if int(path.name[:4])<=5: (baseline/path.name).write_bytes(path.read_bytes())
    migrate('prod','127.0.0.1',6179,baseline)
    owner,knowledge,opinion,reference,attachment,unit,collection=(uuid4() for _ in range(7))
    now=datetime.now(timezone.utc)
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'memo_legacy','unchanged-hash')",(owner,))
        db.execute("INSERT INTO app.user_profiles(user_id,display_name) VALUES(%s,'原资料')",(owner,))
        db.execute("INSERT INTO app.auth_sessions(id,user_id,token_hash,csrf_token,expires_at) VALUES(%s,%s,%s,'unchanged-token',now()+interval '1 day')",(uuid4(),owner,b'x'*32))
        for entity,kind in ((knowledge,'knowledge'),(opinion,'opinion'),(reference,'reference')):
            db.execute('''INSERT INTO app.cards(id,owner_id,code,kind,form,title,question_md,answer_md,body_md,search_text,client_request_id,creation_request_digest)
                VALUES(%s,%s,%s,%s,%s,'原内容',%s,%s,%s,'原内容',%s,%s)''',
                (entity,owner,str(entity),kind,'qa' if kind=='knowledge' else None,'原问题' if kind=='knowledge' else None,'原答案' if kind=='knowledge' else None,'原始正文' if kind!='knowledge' else None,uuid4(),'0'*64))
        db.execute("INSERT INTO app.attachments(id,owner_id,original_key,thumbnail_key,original_bytes,thumbnail_bytes,original_sha256,thumbnail_sha256,mime_type,width,height,status,client_request_id,request_sha256) VALUES(%s,%s,'original/test.png','thumbnail/test.webp',100,80,%s,%s,'image/png',10,20,'ready',%s,%s)",(attachment,owner,'a'*64,'b'*64,uuid4(),'a'*64))
        db.execute('INSERT INTO app.card_attachments(owner_id,card_id,attachment_id,position) VALUES(%s,%s,%s,0)',(owner,reference,attachment))
        db.execute("INSERT INTO app.card_links(owner_id,source_card_id,target_card_id,origin) VALUES(%s,%s,%s,'manual')",(owner,opinion,reference))
        db.execute('INSERT INTO app.review_units(id,owner_id,card_id,cloze_index) VALUES(%s,%s,%s,0)',(unit,owner,knowledge))
        db.execute('INSERT INTO app.review_states(owner_id,unit_id,due_at,scheduler_payload,scheduler_version) VALUES(%s,%s,%s,%s,%s)',(owner,unit,now,Jsonb(fresh(now)),VERSION))
        db.execute("INSERT INTO app.collections(id,owner_id,title,client_request_id,creation_request_digest) VALUES(%s,%s,'原合集',%s,%s)",(collection,owner,uuid4(),'0'*64))
        db.execute('INSERT INTO app.collection_items(id,owner_id,collection_id,card_id,position) VALUES(%s,%s,%s,%s,0)',(uuid4(),owner,collection,reference))
        columns=db.execute("SELECT table_name,array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='app' GROUP BY table_name").fetchall()
        before={name:db.execute(sql.SQL('SELECT {} FROM app.{} ORDER BY 1').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.Identifier(name))).fetchall() for name,names in columns}
    assert migrate('prod','127.0.0.1',6179)==['0006_memo_cards']
    assert migrate('prod','127.0.0.1',6179)==[]
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        for name,names in columns:
            if name=='schema_migrations': continue
            assert before[name]==db.execute(sql.SQL('SELECT {} FROM app.{} ORDER BY 1').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.Identifier(name))).fetchall(),name
        assert db.execute('SELECT memo_format FROM app.cards').fetchall()==[(None,),(None,),(None,)]
        assert db.execute('SELECT count(*) FROM app.memo_items').fetchone()==(0,)
