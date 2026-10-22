from datetime import datetime,timezone
import os
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
from app.db_migrate import migrate,MIGRATIONS_DIR
from app.db_bootstrap import bootstrap,Target
from app.services.scheduling import fresh,VERSION
from test_card_migration_rehearsal import reset_disposable_prod,DSN
from test_auth_integration import isolated_database


def test_upgrade_preserves_existing_cards_links_and_review_state(tmp_path,monkeypatch):
    monkeypatch.setenv('SELFLORE_MIGRATOR_PASSWORD',str(uuid4())); monkeypatch.setenv('SELFLORE_APP_PASSWORD',str(uuid4()))
    bootstrap(Target('prod','127.0.0.1',6179,'postgres')); reset_disposable_prod()
    baseline=tmp_path/'baseline'; baseline.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob('*.sql')):
        if int(path.name[:4])<5: (baseline/path.name).write_bytes(path.read_bytes())
    migrate('prod','127.0.0.1',6179,baseline)
    user,knowledge,opinion,unit=uuid4(),uuid4(),uuid4(),uuid4()
    now=datetime.now(timezone.utc)
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'legacy','unchanged')",(user,))
        for entity,kind in ((knowledge,'knowledge'),(opinion,'opinion')):
            db.execute('''INSERT INTO app.cards(id,owner_id,code,kind,form,title,question_md,answer_md,body_md,search_text,client_request_id,creation_request_digest)
                        VALUES(%s,%s,%s,%s,%s,'历史内容',%s,%s,%s,'历史内容',%s,%s)''',
                       (entity,user,str(entity),kind,'qa' if kind=='knowledge' else None,'原问题' if kind=='knowledge' else None,'原答案' if kind=='knowledge' else None,'原观点' if kind=='opinion' else None,uuid4(),'0'*64))
        db.execute("INSERT INTO app.card_links(owner_id,source_card_id,target_card_id,origin) VALUES(%s,%s,%s,'manual')",(user,opinion,knowledge))
        db.execute('INSERT INTO app.review_units(id,owner_id,card_id,cloze_index) VALUES(%s,%s,%s,0)',(unit,user,knowledge))
        db.execute('INSERT INTO app.review_states(owner_id,unit_id,due_at,scheduler_payload,scheduler_version) VALUES(%s,%s,%s,%s,%s)',(user,unit,now,Jsonb(fresh(now)),VERSION))
        before=db.execute('SELECT id,owner_id,code,kind,question_md,answer_md,body_md,revision FROM app.cards ORDER BY id').fetchall()
        review=db.execute('SELECT * FROM app.review_states').fetchall()
        links=db.execute('SELECT * FROM app.card_links').fetchall()
    assert migrate('prod','127.0.0.1',6179)==['0005_reference_media','0006_memo_cards','0007_unified_card_tags']
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert before==db.execute('SELECT id,owner_id,code,kind,question_md,answer_md,body_md,revision FROM app.cards ORDER BY id').fetchall()
        assert review==db.execute('SELECT * FROM app.review_states').fetchall()
        assert links==db.execute('SELECT * FROM app.card_links').fetchall()
        assert db.execute('SELECT note_md,source_author FROM app.cards').fetchall()==[(None,None),(None,None)]
