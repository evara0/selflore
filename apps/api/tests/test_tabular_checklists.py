import os
from uuid import uuid4

import psycopg
import pytest
from app.db_migrate import MIGRATIONS_DIR, migrate
from app.db_bootstrap import Target, bootstrap
from app.schema_capability import ready, compatible, CAPABILITY
from app.services.cards import digest
from app.schemas.workspace import CardCreate
from test_auth_integration import isolated_database, csrf
from test_workspace_integration import account, create, patch, new_collection
from test_memos import item, memo, complete
from test_card_migration_rehearsal import reset_disposable_prod, DSN


def test_tabular_reload_hide_old_patch_search_sort_and_tags():
    http=account(); target,_=create(http,'knowledge')
    tag=http.post('/api/tags',json={'name':'命令学习'},headers=csrf(http)).json()
    rows=[item('crontab -l',extra_values=['Linux / macOS','查看当前用户计划'],target_ids=[target['id']]),
          item('systemctl list-timers',extra_values=['Linux','查看systemd定时器']),
          item('schtasks',extra_values=['Windows','查看Windows计划'])]
    card,body=memo(http,rows,memo_columns=['命令','适用系统','简要说明'],memo_column_count=3,taxonomy_mode='unified',tag_ids=[tag['id']])
    assert http.post('/api/cards',json=body,headers=csrf(http)).json()['id']==card['id']
    card=http.get('/api/cards/'+card['id']).json()
    assert card['memo_columns']==['命令','适用系统','简要说明'] and card['memo_items'][2]['extra_values']==['Windows','查看Windows计划']
    assert card['tag_ids']==[tag['id']]
    card=patch(http,card,memo_column_count=1).json()
    legacy=[{k:r[k] for k in ('id','text','is_completed','target_ids')} for r in card['memo_items']]
    legacy[0]['text']='crontab -l（更新）'
    card=patch(http,card,memo_items=legacy).json()
    assert card['memo_column_count']==1 and card['memo_items'][0]['extra_values']==rows[0]['extra_values']
    assert http.get('/api/cards',params={'q':'Windows计划'}).json()['total']==1
    tasks=http.get('/api/memo-items',params={'q':'Windows计划'}).json()
    assert tasks['total']==1 and tasks['items'][0]['text']=='schtasks'
    assert tasks['items'][0]['memo_columns']==card['memo_columns']
    card=patch(http,card,memo_column_count=3).json()
    before=http.get('/api/reviews/summary').json()
    card=complete(http,card,card['memo_items'][0]).json()
    assert http.get('/api/reviews/summary').json()==before
    order=[r['id'] for r in reversed(card['memo_items'])]
    card=http.put(f"/api/cards/{card['id']}/memo-items/order",json={'expected_revision':card['revision'],'item_ids':order},headers=csrf(http)).json()
    assert card['memo_items'][-1]['is_completed'] and card['memo_items'][-1]['target_ids']==[target['id']]
    assert card['memo_items'][0]['extra_values']==rows[2]['extra_values']
    group=new_collection(http)
    http.post(f"/api/collections/{group['id']}/items",json={'expected_revision':1,'card_ids':[card['id']]},headers=csrf(http))
    assert http.get(f"/api/collections/{group['id']}/items").json()['items'][0]['memo_items']==card['memo_items']
    for values in ({'memo_column_count':0},{'memo_column_count':4},{'memo_columns':['a']},{'memo_columns':['a','','b']},{'memo_items':[item(extra_values=['x'*2001,''])]},{'memo_items':[item(extra_values=[''])]}):
        assert patch(http,card,**values).status_code==422
        assert http.get('/api/cards/'+card['id']).json()['revision']==card['revision']


def test_new_links_knowledge_only_and_legacy_creation_retry():
    http=account(); knowledge,_=create(http,'knowledge'); ref,_=create(http,'reference',body_md='合成资料')
    card,body=memo(http,[item()])
    row=card['memo_items'][0]
    assert patch(http,card,memo_items=[{**item(), 'target_ids':[ref['id']]}]).status_code==422
    assert patch(http,card,memo_items=[{**item(), 'target_ids':[knowledge['id']]}]).status_code==200
    old=CardCreate.model_validate(body).model_dump(mode='json',exclude={'memo_columns','memo_column_count'})
    for entry in old['memo_items']: entry.pop('extra_values')
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute('UPDATE app.cards SET creation_request_digest=%s WHERE id=%s',(digest(old),card['id']))
    assert http.post('/api/cards',json=body,headers=csrf(http)).json()['id']==card['id']


def test_0007_upgrade_preserves_legacy_row_and_backup_contract(tmp_path, monkeypatch):
    monkeypatch.setenv('SELFLORE_MIGRATOR_PASSWORD',str(uuid4()))
    monkeypatch.setenv('SELFLORE_APP_PASSWORD',str(uuid4()))
    bootstrap(Target('prod','127.0.0.1',6179,'postgres')); reset_disposable_prod()
    baseline=tmp_path/'baseline'; baseline.mkdir()
    for path in MIGRATIONS_DIR.glob('*.sql'):
        if int(path.name[:4])<=7: (baseline/path.name).write_bytes(path.read_bytes())
    migrate('prod','127.0.0.1',6179,baseline)
    owner,card,row,request=(uuid4() for _ in range(4))
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert not ready(db)
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        db.execute("INSERT INTO app.users(id,username,password_hash) VALUES(%s,'legacy_table','hash')",(owner,))
        db.execute("INSERT INTO app.cards(id,owner_id,code,kind,memo_format,title,search_text,client_request_id,creation_request_digest) VALUES(%s,%s,'legacy','memo','checklist','旧清单','旧条目',%s,%s)",(card,owner,request,'0'*64))
        db.execute("INSERT INTO app.memo_items(id,owner_id,memo_card_id,text,position,is_completed,completed_at) VALUES(%s,%s,%s,'旧条目',0,true,now())",(row,owner,card))
        before=db.execute('SELECT id,text,position,is_completed,completed_at FROM app.memo_items').fetchall()
    assert migrate('prod','127.0.0.1',6179)==['0008_tabular_checklists','0009_card_import_batches']
    assert migrate('prod','127.0.0.1',6179)==[]
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE selflore_prod_owner')
        assert ready(db)
        assert db.execute('SELECT id,text,position,is_completed,completed_at FROM app.memo_items').fetchall()==before
        assert db.execute('SELECT extra_values FROM app.memo_items').fetchone()[0]==['','']
        assert db.execute('SELECT memo_column_count,memo_columns FROM app.cards').fetchone()==(1,['条目','字段 2','字段 3'])
        for statement,args in [('UPDATE app.cards SET memo_column_count=4',()),('UPDATE app.cards SET memo_columns=%s',(['a','b'],)),('UPDATE app.memo_items SET extra_values=%s',(['x'*2001,''],))]:
            with pytest.raises(psycopg.errors.CheckViolation),db.transaction(): db.execute(statement,args)
    assert compatible(CAPABILITY) and not compatible('reference-memo-tags-v1')
