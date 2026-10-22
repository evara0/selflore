import os
from uuid import uuid4
import psycopg
import pytest
from test_auth_integration import isolated_database, csrf
from test_workspace_integration import account, create, patch
from app.services.tags import normalize_name


def tag(http,name):
    response=http.post('/api/tags',json={'name':name},headers=csrf(http))
    assert response.status_code==201,response.text
    return response.json()['id']


def test_shared_optional_tags_filters_and_conflicts():
    http=account(); a,b=tag(http,'人工智能'),tag(http,'LLM')
    cards=[]
    for kind,extra in [('knowledge',{}),('reference',{}),('opinion',{}),('memo',{'memo_format':'note'})]:
        card,_=create(http,kind,taxonomy_mode='unified',tag_ids=[a,b],**extra)
        cards.append(card)
        assert set(card['tag_ids'])=={a,b} and card['topics']==[]
    empty,_=create(http,'reference',taxonomy_mode='unified')
    assert empty['tag_ids']==[]
    for mode in ('all','any'):
        response=http.get('/api/cards',params=[('tag_ids',a),('tag_ids',b),('tag_match',mode)]).json()
        assert response['total']==4
    assert len(http.get('/api/reviews/queue',params={'tag_ids':a}).json()['items'])==1
    assert http.get('/api/tags').json()['items'][0]['card_count']==4
    c=cards[0]
    saved=patch(http,c,taxonomy_mode='unified',tag_ids=[a]).json()
    assert saved['tag_ids']==[a]
    assert patch(http,c,taxonomy_mode='unified',tag_ids=[]).status_code==409
    assert http.get('/api/cards',params=[('tag_ids',a),('tag_ids',b)]).json()['total']==3
    assert http.get('/api/cards',params=[('tag_ids',a),('tag_ids',b),('tag_match','any')]).json()['total']==4
    assert patch(http,saved,taxonomy_mode='unified',topic_ids=[]).status_code==422
    assert patch(http,saved,taxonomy_mode='unified',tag_ids=[a,a]).status_code==422
    assert http.get('/api/cards',params=[('tag_ids',a),('tag_ids',a)]).json()['total']==4
    assert http.get('/api/cards',params={'tag_ids':a,'topic_id':uuid4()}).status_code==422
    assert http.get('/api/cards',params={'tag_match':'wrong'}).status_code==422


def test_legacy_partitions_rename_delete_and_owner_isolation():
    http=account(); other=account('other'); old=http.post('/api/topics',json={'kind':'knowledge','name':'ＡＩ'},headers=csrf(http))
    assert old.headers['Deprecation']=='true'
    topic=old.json(); canonical=topic['tag_id']; extra=tag(http,'额外')
    assert http.post('/api/topics',json={'kind':'knowledge','name':'AI'},headers=csrf(http)).status_code==409
    assert http.post('/api/tags',json={'name':' AI '},headers=csrf(http)).json()['detail']['existing_tag']['id']==canonical
    card,_=create(http,topic_ids=[topic['id']])
    reference,_=create(http,'reference',taxonomy_mode='unified',tag_ids=[canonical])
    assert http.get('/api/cards',params={'topic_id':topic['id']}).json()['total']==1
    assert http.get('/api/cards',params={'tag_id':canonical}).json()['total']==2
    updated=patch(http,card,taxonomy_mode='unified',tag_ids=[canonical,extra]).json()
    updated=patch(http,updated,topic_ids=[]).json()
    assert set(updated['tag_ids'])=={canonical,extra}
    updated=patch(http,updated,tag_ids=[]).json()
    assert set(updated['tag_ids'])=={canonical,extra}
    assert http.patch('/api/topics/'+topic['id'],json={'name':'改名'},headers=csrf(http)).status_code==200
    assert http.get('/api/cards/'+reference['id']).json()['tags'][0]['name']=='改名'
    assert http.delete('/api/topics/'+topic['id'],headers=csrf(http)).status_code==409
    foreign=tag(other,'额外')
    for entity in (foreign,str(uuid4())):
        response=http.get('/api/cards',params={'tag_ids':entity})
        assert response.status_code==404 and response.json()['detail']['code']=='not_found'
        assert patch(http,updated,taxonomy_mode='unified',tag_ids=[entity]).status_code==404
    assert http.get('/api/cards/'+updated['id']).json()['tag_ids']==updated['tag_ids']
    assert tag(other,'改名')!=canonical


def test_limits_memo_parent_filter_and_database_normalization():
    http=account(); ids=[tag(http,str(i)) for i in range(31)]
    card,_=create(http,'opinion',taxonomy_mode='unified',tag_ids=ids[:30])
    assert len(card['tag_ids'])==30
    assert patch(http,card,taxonomy_mode='unified',tag_ids=ids).status_code==422
    assert http.get('/api/cards',params=[('tag_ids',i) for i in ids]).status_code==422
    memo,_=create(http,'memo',memo_format='checklist',memo_items=[{'id':str(uuid4()),'text':'一项'},{'id':str(uuid4()),'text':'另一项'}],taxonomy_mode='unified',tag_ids=[ids[0]])
    result=http.get('/api/memo-items',params={'tag_ids':ids[0],'limit':1}).json()
    assert result['total']==2 and result['items'][0]['memo_card_id']==memo['id']
    assert http.get('/api/memo-items',params={'tag_ids':ids[1]}).json()['total']==0
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        for value in ['\u3000ＡＩ\u0085','\u001c \tLLM\r\n','a  b','字'*80]:
            assert db.execute('SELECT app.normalize_tag_name(%s)',(value,)).fetchone()[0]==normalize_name(value)
        with pytest.raises(psycopg.errors.CheckViolation):
            with db.transaction():
                db.execute('INSERT INTO app.card_tags(owner_id,card_id,tag_id) VALUES(%s,%s,%s)',(http.get('/api/auth/me').json()['id'],card['id'],ids[30]))
                db.execute('SET CONSTRAINTS ALL IMMEDIATE')
    other=account('other')
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with db.transaction():
                db.execute('INSERT INTO app.card_tags(owner_id,card_id,tag_id) VALUES(%s,%s,%s)',(other.get('/api/auth/me').json()['id'],card['id'],ids[0]))
