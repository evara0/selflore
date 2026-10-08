from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import os
from uuid import uuid4
import psycopg
import pytest
from app.main import create_app
from app.services import profiles
from app.db_migrate import migrate,MIGRATIONS_DIR,MigrationError,GRANTS
from fastapi.testclient import TestClient
from test_auth_integration import isolated_database,register,login,csrf


def account(name='alice'):
    http=TestClient(create_app())
    assert register(http,name).status_code==201
    assert login(http,name).status_code==200
    return http


def create(http,kind='knowledge',**extra):
    payload={'kind':kind,'title':'什么是主动回忆？','client_request_id':str(uuid4())}
    if kind=='knowledge': payload.update(form='qa',question_md='主动回忆是什么？',answer_md='从记忆中主动提取信息。')
    else: payload.update(body_md='理解比收藏更重要。')
    payload.update(extra)
    response=http.post('/api/cards',json=payload,headers=csrf(http))
    assert response.status_code==201,response.text
    return response.json(),payload


def patch(http,card,**extra):
    return http.patch('/api/cards/'+card['id'],json={'expected_revision':card['revision'],**extra},headers=csrf(http))


def new_collection(http):
    response=http.post('/api/collections',json={'title':'学会学习','client_request_id':str(uuid4())},headers=csrf(http))
    assert response.status_code==201,response.text
    return response.json()


def test_authentication_and_write_protection():
    with TestClient(create_app()) as http:
        assert http.get('/api/cards').status_code==401
    http=account()
    assert http.post('/api/cards',json={},headers={'Origin':'https://untrusted.example'}).status_code==403
    assert http.post('/api/cards',json={},headers={'Origin':'http://127.0.0.1:24566'}).status_code==403
    assert http.post('/api/cards',json={'owner_id':str(uuid4())},headers=csrf(http)).status_code==422


def test_creation_search_and_idempotency_after_edit():
    http=account(); card,payload=create(http,title='主动回忆 100%_方法')
    assert 'answer_md' not in http.get('/api/cards').json()['items'][0]
    assert http.get('/api/cards',params={'q':'100%_'}).json()['total']==1
    assert http.get('/api/cards',params={'q':'100%_不存在'}).json()['total']==0
    edited=patch(http,card,title='改名').json()
    retry=http.post('/api/cards',json=payload,headers=csrf(http))
    assert retry.json()['id']==edited['id']
    assert retry.json()['title']=='改名'
    assert http.get('/api/cards').json()['total']==1
    assert http.post('/api/cards',json={**payload,'title':'不同载荷'},headers=csrf(http)).status_code==409
    assert patch(http,card,title='覆盖').status_code==409


def test_concurrent_creation_and_edits():
    http=account(); card,payload=create(http)
    headers=csrf(http)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(lambda _:http.post('/api/cards',json=payload,headers=headers).status_code,range(2)))
    assert result==[201,201]
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(lambda title:http.patch('/api/cards/'+card['id'],json={'title':title,'expected_revision':1},headers=headers).status_code,['一','二']))
    assert sorted(result)==[200,409]


def test_two_user_isolation_and_database_relationship_constraints():
    alice,bob=account(),account('bob')
    own,_=create(alice); other,_=create(bob)
    assert alice.get('/api/cards/'+other['id']).status_code==404
    assert alice.get('/api/cards').json()['total']==1
    assert alice.post('/api/cards/'+own['id']+'/links/'+other['id'],json={'expected_revision':1},headers=csrf(alice)).status_code==404
    group=new_collection(alice)
    assert alice.post('/api/collections/'+group['id']+'/items',json={'expected_revision':1,'card_ids':[own['id'],other['id']]},headers=csrf(alice)).status_code==404
    assert alice.get('/api/collections/'+group['id']+'/items').json()['items']==[]
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        owner=alice.get('/api/auth/me').json()['id']
        with pytest.raises(psycopg.errors.ForeignKeyViolation),db.transaction():
            db.execute("INSERT INTO app.card_links(owner_id,source_card_id,target_card_id,origin) VALUES(%s,%s,%s,'manual')",(owner,own['id'],other['id']))


def test_topics_tags_and_safe_delete():
    http=account()
    topic=http.post('/api/topics',json={'name':'认知科学','kind':'knowledge'},headers=csrf(http)).json()
    other=http.post('/api/topics',json={'name':'另一分类','kind':'knowledge'},headers=csrf(http)).json()
    tag=http.post('/api/tags',json={'name':'记忆'},headers=csrf(http)).json()
    card,_=create(http,topic_ids=[topic['id']],tag_ids=[tag['id']])
    assert http.get('/api/cards',params={'topic_id':topic['id']}).json()['total']==1
    assert http.delete('/api/topics/'+topic['id'],headers=csrf(http)).status_code==409
    assert patch(http,card,topic_ids=[topic['id'],other['id']]).status_code==422
    assert patch(http,card,topic_ids=[],tag_ids=[]).status_code==200
    assert http.delete('/api/topics/'+topic['id'],headers=csrf(http)).status_code==204


def test_links_rename_source_removal_and_backlinks():
    http=account(); target,_=create(http)
    opinion,_=create(http,'opinion',body_md='参见 [['+target['id']+'|主动回忆]]')
    assert len(http.get('/api/cards/'+target['id']+'/links').json()['incoming'])==1
    result=http.post('/api/cards/'+opinion['id']+'/links/'+target['id'],json={'expected_revision':1},headers=csrf(http)).json()
    assert len(http.get('/api/cards/'+opinion['id']+'/links').json()['outgoing'])==1
    assert patch(http,target,title='新的标题').status_code==200
    assert patch(http,result,body_md='移除正文链接').status_code==200
    assert http.get('/api/cards/'+opinion['id']+'/links').json()['outgoing'][0]['title']=='新的标题'
    assert http.get('/api/cards',params={'kind':'opinion','sort':'connections_desc'}).status_code==200


def test_cloze_unit_changes_preserve_state_and_content_counts():
    http=account()
    card,_=create(http,form='cloze',question_md=None,answer_md=None,body_md='{{c1::主动}} {{c1::回忆}} {{c2::间隔}}')
    queue=http.get('/api/reviews/queue').json()['items']
    assert len(queue)==2
    first=next(u for u in queue if u['cloze_index']==1)
    payload={'request_id':str(uuid4()),'rating':3,'expected_state_version':first['state_version'],'expected_content_revision':card['revision']}
    assert http.post('/api/reviews/units/'+first['id']+'/ratings',json=payload,headers=csrf(http)).status_code==200
    updated=patch(http,card,body_md='{{c1::主动}} {{c3::理解}}').json()
    new_queue=http.get('/api/reviews/queue').json()['items']
    assert [u['cloze_index'] for u in new_queue]==[3]
    assert http.get('/api/me/summary').json()['knowledge']==1
    assert http.get('/api/me/heatmap').json()['days'][-1]['is_future'] in (True,False)
    assert patch(http,updated,body_md='{{c1::主动}} {{c2::重引入}}').status_code==200
    assert any(u['cloze_index']==2 and u['state']=='new' for u in http.get('/api/reviews/queue').json()['items'])


def test_rating_idempotency_stale_content_and_read_only_preview():
    http=account(); card,_=create(http)
    unit=http.get('/api/reviews/queue').json()['items'][0]
    assert http.get('/api/reviews/units/'+unit['id']+'/preview').status_code==200
    assert http.get('/api/reviews/summary').json()['today_completed']==0
    data={'request_id':str(uuid4()),'rating':3,'expected_state_version':unit['state_version'],'expected_content_revision':card['revision']}
    headers=csrf(http)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:http.post('/api/reviews/units/'+unit['id']+'/ratings',json=data,headers=headers),range(2)))
    assert all(r.status_code==200 for r in results)
    assert results[0].json()==results[1].json()
    assert http.get('/api/reviews/summary').json()['today_completed']==1
    assert http.post('/api/reviews/units/'+unit['id']+'/ratings',json={**data,'rating':1},headers=headers).status_code==409
    assert http.post('/api/reviews/units/'+unit['id']+'/ratings',json={**data,'request_id':str(uuid4())},headers=headers).status_code==409
    updated=patch(http,card,question_md='更新问题').json()
    assert updated['revision']==2


def test_collection_reorder_invalid_batch_lifecycle_restore():
    http=account(); a,_=create(http); b,_=create(http,'opinion')
    group=new_collection(http)
    uri='/api/collections/'+group['id']
    group=http.post(uri+'/items',json={'expected_revision':1,'card_ids':[a['id'],b['id']]},headers=csrf(http)).json()
    directory=http.get(uri+'/items').json()['items']; ids=[r['item_id'] for r in directory]
    assert http.put(uri+'/order',json={'expected_revision':group['revision'],'item_ids':[ids[0],ids[0]]},headers=csrf(http)).status_code==422
    group=http.put(uri+'/order',json={'expected_revision':group['revision'],'item_ids':ids[::-1]},headers=csrf(http)).json()
    assert http.get(uri+'/items').json()['items'][0]['id']==b['id']
    trashed=http.post('/api/cards/'+a['id']+'/lifecycle',json={'expected_revision':a['revision'],'action':'trash'},headers=csrf(http)).json()
    assert http.get(uri).json()['available_items']==1
    assert next(r for r in http.get(uri+'/items').json()['items'] if r['id']==a['id'])['answer_md'] is None
    http.post('/api/cards/'+a['id']+'/lifecycle',json={'expected_revision':trashed['revision'],'action':'restore'},headers=csrf(http))
    assert http.get(uri).json()['available_items']==2
    assert http.request('DELETE',uri+'/items/'+ids[0],json={'expected_revision':group['revision']},headers=csrf(http)).status_code==200
    assert http.get('/api/cards/'+a['id']).status_code==200


def test_profile_heatmap_and_nonlearning_events():
    http=account(); card,_=create(http)
    before=http.get('/api/me/profile').json()
    assert before['display_name']=='alice'
    assert http.patch('/api/me/profile',json={'expected_revision':1,'display_name':'我的知识花园','timezone':'Asia/Shanghai'},headers=csrf(http)).status_code==200
    assert http.patch('/api/me/profile',json={'expected_revision':1,'display_name':'冲突'},headers=csrf(http)).status_code==409
    assert patch(http,card,is_bookmarked=True).status_code==200
    heat=http.get('/api/me/heatmap').json()
    assert len(heat['days'])==84
    assert sum(row['count'] for row in heat['days'])==1
    assert http.get('/api/me/summary').json()['streak']==1
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        owner=http.get('/api/auth/me').json()['id']
        fixed=datetime(2026,10,4,15,tzinfo=timezone.utc)
        assert len(profiles.heatmap(db,owner,fixed)['days'])==84


def test_migration_history_missing_and_permissions(tmp_path):
    with pytest.raises(MigrationError,match='缺失'):
        (tmp_path/'0001_identity.sql').write_bytes((MIGRATIONS_DIR/'0001_identity.sql').read_bytes())
        migrate('dev','127.0.0.1',6179,tmp_path)
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        for version,grants in GRANTS.items():
            if version=='0001_identity': continue
            for table,privileges in grants.items():
                assert db.execute('SELECT has_table_privilege(current_user,%s,%s)',('app.'+table,privileges)).fetchone()[0]
                assert not db.execute("SELECT has_table_privilege(current_user,%s,'TRUNCATE')",('app.'+table,)).fetchone()[0]
        assert not db.execute("SELECT has_table_privilege(current_user,'app.review_logs','UPDATE')").fetchone()[0]
        assert not db.execute("SELECT has_schema_privilege(current_user,'app','CREATE')").fetchone()[0]
