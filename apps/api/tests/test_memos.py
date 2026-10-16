import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from app.schemas.workspace import CardCreate
from app.services.cards import digest
from test_auth_integration import isolated_database, csrf
from test_workspace_integration import account, create, patch, new_collection


def item(text='待学项目', **values):
    return {'id':str(uuid4()),'text':text,**values}


def memo(http, rows=None, **values):
    body={'kind':'memo','memo_format':'checklist' if rows is not None else 'note','title':'学习备忘','client_request_id':str(uuid4()),**values}
    if rows is not None: body['memo_items']=rows
    response=http.post('/api/cards',json=body,headers=csrf(http))
    assert response.status_code==201,response.text
    return response.json(),body


def complete(http, card, row, value=True, revision=None):
    return http.patch(f"/api/cards/{card['id']}/memo-items/{row['id']}",json={'expected_revision':revision or card['revision'],'is_completed':value},headers=csrf(http))


def test_note_and_checklist_idempotency_search_and_stats():
    http=account()
    note,_=memo(http)
    assert note['body_md'] is None and note['memo_items']==[]
    card,body=memo(http,[item('独特检索词'),item('独特检索词第二项')])
    again=http.post('/api/cards',json=body,headers=csrf(http))
    assert again.json()['id']==card['id'] and again.json()['memo_items']==card['memo_items']
    assert http.get('/api/cards',params={'kind':'memo','q':'独特检索词'}).json()['total']==1
    assert http.get('/api/cards',params={'kind':'memo','memo_format':'note'}).json()['total']==1
    assert http.get('/api/cards',params={'kinds':'knowledge,reference,opinion'}).json()['total']==0
    assert http.get('/api/memo-items').json()['total']==2
    assert http.get('/api/me/summary').json()['memos']==2
    assert http.get('/api/me/summary').json()['streak']==0
    assert all(d['count']==0 for d in http.get('/api/me/heatmap').json()['days'])
    assert http.get('/api/reviews/summary').json()['new_units']==0
    assert http.get('/api/me/activity',params={'kind':'memo'}).json()['total']==2


def test_completion_noop_conflict_reopen_and_edit_preserve():
    http=account(); card,_=memo(http,[item(),item('另一项')]); row=card['memo_items'][0]
    done=complete(http,card,row); assert done.status_code==200,done.text
    changed=done.json(); timestamp=changed['memo_items'][0]['completed_at']
    assert timestamp and changed['memo_progress']=={'total':2,'completed':1}
    noop=complete(http,changed,row).json()
    assert noop['revision']==changed['revision'] and noop['memo_items'][0]['completed_at']==timestamp
    assert complete(http,card,row).status_code==409
    bookmark=patch(http,changed,is_bookmarked=True).json()
    assert bookmark['memo_items'][0]['completed_at']==timestamp
    rows=[{k:r[k] for k in ('id','text','is_completed','target_ids')} for r in bookmark['memo_items']]
    rows[0]['text']='修改文字'
    updated=patch(http,bookmark,memo_items=rows).json()
    assert updated['memo_items'][0]['completed_at']==timestamp
    reopened=complete(http,updated,row,False).json()
    assert reopened['memo_items'][0]['completed_at'] is None
    assert reopened['processing_state']=='inbox'
    assert http.get('/api/memo-items').json()['total']==2
    kinds=[e['event_kind'] for e in http.get('/api/me/activity').json()['items']]
    assert kinds.count('memo_item_completed')==1 and kinds.count('memo_item_reopened')==1


def test_reorder_links_sources_and_restoration():
    http=account(); target,_=create(http,'reference',body_md='原始资料')
    first=item(target_ids=[target['id']]); second=item('第二项',target_ids=[target['id']],is_completed=True)
    card,_=memo(http,[first,second],body_md=f"[[{target['id']}|资料]]")
    assert http.post(f"/api/cards/{card['id']}/links/{target['id']}",json={'expected_revision':card['revision']},headers=csrf(http)).status_code==200
    card=http.get(f"/api/cards/{card['id']}").json()
    links=http.get(f"/api/cards/{target['id']}/links").json()['incoming']
    assert len(links)==1 and set(links[0]['origins'])=={'inline','manual','item'} and len(links[0]['item_links'])==2
    order=f"/api/cards/{card['id']}/memo-items/order"
    assert http.put(order,json={'expected_revision':card['revision'],'item_ids':[first['id']]},headers=csrf(http)).status_code==422
    ordered=http.put(order,json={'expected_revision':card['revision'],'item_ids':[second['id'],first['id']]},headers=csrf(http))
    assert ordered.status_code==200,ordered.text
    card=ordered.json(); assert card['memo_items'][0]['id']==second['id'] and card['memo_items'][0]['completed_at']
    removed=patch(http,card,memo_items=[{k:card['memo_items'][1][k] for k in ('id','text','is_completed','target_ids')}],body_md=None).json()
    links=http.get(f"/api/cards/{target['id']}/links").json()['incoming']
    assert set(links[0]['origins'])=={'manual','item'} and len(links[0]['item_links'])==1
    card=removed
    for action in ('archive','restore','trash','restore'):
        response=http.post(f"/api/cards/{card['id']}/lifecycle",json={'expected_revision':card['revision'],'action':action},headers=csrf(http))
        assert response.status_code==200,response.text
        card=response.json()
        assert card['memo_items'][0]['id']==first['id']
        if action in ('archive','trash'):
            assert complete(http,card,first).status_code==409
            assert patch(http,card,title='不应改').status_code==409
            assert http.get('/api/memo-items').json()['total']==0
        else: assert http.get('/api/memo-items').json()['total']==1


def test_pagination_item_search_and_collection_reading():
    http=account(); card,_=memo(http,[item('匹配项 '+str(i)) for i in range(25)],title='学习清单')
    page=http.get('/api/memo-items',params={'limit':12,'offset':24}).json()
    assert page['total']==25 and len(page['items'])==1
    assert http.get('/api/memo-items',params={'q':'匹配项 24'}).json()['total']==1
    assert http.get('/api/memo-items',params={'q':'学习清单'}).json()['total']==25
    assert http.get('/api/memo-items',params={'q':'不匹配'}).json()['total']==0
    group=new_collection(http)
    assert http.post(f"/api/collections/{group['id']}/items",json={'expected_revision':1,'card_ids':[card['id']]},headers=csrf(http)).status_code==200
    assert http.get(f"/api/collections/{group['id']}").json()['memo_count']==1
    before=http.get('/api/me/activity').json()['total']
    assert len(http.get(f"/api/collections/{group['id']}/items").json()['items'][0]['memo_items'])==25
    assert http.get('/api/me/activity').json()['total']==before

    second=new_collection(http)
    assert http.post(f"/api/collections/{second['id']}/items",json={'expected_revision':1,'card_ids':[card['id']]},headers=csrf(http)).status_code==200
    updated=complete(http,card,card['memo_items'][0]).json()
    for collection in (group,second):
        member=http.get(f"/api/collections/{collection['id']}/items").json()['items'][0]
        assert member['memo_progress']=={'total':25,'completed':1}
        assert member['memo_items'][0]['completed_at']==updated['memo_items'][0]['completed_at']


def test_ownership_atomicity_concurrency_and_input_boundaries():
    alice=account(); bob=account('bob')
    foreign,_=memo(bob,[item()]); card,_=memo(alice,[item()]); old=card['memo_items'][0]
    assert complete(bob,card,old).status_code==404
    assert patch(alice,card,memo_items=[item(target_ids=[foreign['id']])]).status_code==404
    assert patch(alice,card,memo_items=[{k:foreign['memo_items'][0][k] for k in ('id','text','is_completed','target_ids')}]).status_code==404
    for rows in ([],[item(' ')],[item('x'*2001)],[item() for _ in range(201)],[item(target_ids=[card['id']])]):
        assert patch(alice,card,memo_items=rows).status_code==422
        assert alice.get(f"/api/cards/{card['id']}").json()['revision']==card['revision']
    assert patch(alice,card,memo_format='note').status_code==422
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda value:complete(alice,card,old,value),[True,True]))
    assert sorted(r.status_code for r in responses)==[200,409]


@pytest.mark.parametrize('legacy_kind',['knowledge','opinion','reference'])
def test_legacy_creation_digests_and_database_constraints(legacy_kind):
    http=account(); card,payload=create(http,legacy_kind,**({'body_md':'原文'} if legacy_kind=='reference' else {}))
    modeled=CardCreate.model_validate(payload).model_dump(mode='json')
    legacy={k:v for k,v in modeled.items() if k not in ('memo_format','memo_items')}
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute('UPDATE app.cards SET creation_request_digest=%s WHERE id=%s',(digest(legacy),card['id']))
    assert http.post('/api/cards',json=payload,headers=csrf(http)).json()['id']==card['id']
    note,_=memo(http)
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        owner=db.execute('SELECT owner_id FROM app.cards WHERE id=%s',(note['id'],)).fetchone()[0]
        with pytest.raises(psycopg.errors.CheckViolation),db.transaction():
            db.execute('INSERT INTO app.memo_items(id,owner_id,memo_card_id,text,position) VALUES(%s,%s,%s,%s,0)',(uuid4(),owner,note['id'],'不能用于普通备忘'))
            db.execute('SET CONSTRAINTS ALL IMMEDIATE')
        with pytest.raises(psycopg.errors.ForeignKeyViolation),db.transaction():
            db.execute('INSERT INTO app.memo_items(id,owner_id,memo_card_id,text,position) VALUES(%s,%s,%s,%s,0)',(uuid4(),owner,card['id'],'不能用于资料'))
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege),db.transaction(): db.execute('TRUNCATE app.memo_items')


def test_database_memo_item_identity_completion_and_empty_invariants():
    http=account(); card,_=memo(http,[item()]); other,_=memo(http,[item()]); row=card['memo_items'][0]
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        for query,args in [
            ('DELETE FROM app.memo_items WHERE id=%s',(row['id'],)),
            ('UPDATE app.memo_items SET memo_card_id=%s WHERE id=%s',(other['id'],row['id'])),
            ('UPDATE app.memo_items SET is_completed=true WHERE id=%s',(row['id'],)),
            ('UPDATE app.memo_items SET position=200 WHERE id=%s',(row['id'],)),
            ('UPDATE app.memo_items SET text=%s WHERE id=%s',(' ',row['id']))]:
            with pytest.raises(psycopg.errors.CheckViolation),db.transaction():
                db.execute(query,args); db.execute('SET CONSTRAINTS ALL IMMEDIATE')
        owner=db.execute('SELECT owner_id FROM app.cards WHERE id=%s',(card['id'],)).fetchone()[0]
        with pytest.raises(psycopg.errors.UniqueViolation),db.transaction():
            db.execute('INSERT INTO app.memo_items(id,owner_id,memo_card_id,text,position) VALUES(%s,%s,%s,%s,0)',(uuid4(),owner,card['id'],'duplicate position'))
            db.execute('SET CONSTRAINTS ALL IMMEDIATE')
        with pytest.raises(psycopg.errors.CheckViolation),db.transaction():
            db.execute('INSERT INTO app.memo_item_links(owner_id,memo_card_id,item_id,target_card_id) VALUES(%s,%s,%s,%s)',(owner,card['id'],row['id'],card['id']))
        with pytest.raises(psycopg.errors.CheckViolation),db.transaction():
            for n in range(21):
                target=uuid4()
                db.execute("INSERT INTO app.cards(id,owner_id,code,kind,memo_format,title,search_text,client_request_id,creation_request_digest) VALUES(%s,%s,%s,'memo','note','target','target',%s,%s)",(target,owner,str(target),uuid4(),'0'*64))
                db.execute('INSERT INTO app.memo_item_links(owner_id,memo_card_id,item_id,target_card_id) VALUES(%s,%s,%s,%s)',(owner,card['id'],row['id'],target))
            db.execute('SET CONSTRAINTS ALL IMMEDIATE')
