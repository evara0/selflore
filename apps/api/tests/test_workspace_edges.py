from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import os
import psycopg
import pytest
from app.services import profiles
from app.services import reviews
from app.admin_bootstrap import create_first_admin
from app.main import create_app
from fastapi.testclient import TestClient
from test_auth_integration import login, PASSWORD
from app.auth import hasher
from test_auth_integration import isolated_database, csrf
from test_workspace_integration import account, create, patch, new_collection


def test_database_content_and_review_foreign_keys():
    http=account(); card,_=create(http); opinion,_=create(http,'opinion')
    unit=http.get('/api/reviews/queue').json()['items'][0]
    owner=http.get('/api/auth/me').json()['id']
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        with pytest.raises(psycopg.errors.CheckViolation),db.transaction():
            db.execute('UPDATE app.cards SET form=NULL WHERE id=%s',(card['id'],))
        with pytest.raises(psycopg.errors.ForeignKeyViolation),db.transaction():
            db.execute('INSERT INTO app.review_units(id,owner_id,card_id,cloze_index) VALUES(%s,%s,%s,0)',(uuid4(),owner,opinion['id']))
        # The log's card must be the exact card of its unit, not just another owned knowledge card.
        other,_=create(http)
        headers=csrf(http)
        data={'request_id':str(uuid4()),'rating':4,'expected_state_version':1,'expected_content_revision':1}
        assert http.post('/api/reviews/units/'+unit['id']+'/ratings',json=data,headers=headers).status_code==200
        with pytest.raises(psycopg.errors.ForeignKeyViolation),db.transaction():
            db.execute('INSERT INTO app.review_logs SELECT %s,owner_id,unit_id,%s,%s,request_digest,rating,reviewed_at,duration_ms,content_revision,state_version_before,scheduler_version,state_before,state_after,content_snapshot,response_payload FROM app.review_logs WHERE owner_id=%s',(uuid4(),other['id'],uuid4(),owner))
        with pytest.raises(psycopg.errors.UniqueViolation),db.transaction():
            db.execute('INSERT INTO app.review_logs SELECT %s,owner_id,unit_id,card_id,request_id,request_digest,rating,reviewed_at,duration_ms,content_revision,state_version_before,scheduler_version,state_before,state_after,content_snapshot,response_payload FROM app.review_logs WHERE owner_id=%s',(uuid4(),owner))


def test_cloze_summary_redacts_answers_and_grade_rejects_old_content():
    http=account(); card,_=create(http,form='cloze',question_md=None,answer_md=None,body_md='{{c1::秘密答案::提示}} 与 {{c2::另一答案}}')
    item=http.get('/api/cards').json()['items'][0]
    assert '秘密答案' not in item['excerpt'] and '另一答案' not in item['excerpt']
    assert '【提示】' in item['excerpt']
    units=http.get('/api/reviews/queue').json()['items']
    updated=patch(http,card,body_md='{{c1::新内容}} 与 {{c2::另一答案}}').json()
    data={'request_id':str(uuid4()),'rating':3,'expected_state_version':units[0]['state_version'],'expected_content_revision':card['revision']}
    assert http.post('/api/reviews/units/'+units[0]['id']+'/ratings',json=data,headers=csrf(http)).status_code==409
    assert http.get('/api/reviews/summary').json()['today_completed']==0
    assert updated['revision']==2


def test_new_allowance_due_priority_and_archived_exclusion():
    http=account(); card,_=create(http); second,_=create(http)
    profile=http.get('/api/me/profile').json()
    assert http.patch('/api/me/profile',json={'expected_revision':profile['revision'],'daily_new_limit':1},headers=csrf(http)).status_code==200
    units=http.get('/api/reviews/queue').json()['items']; assert len(units)==1
    first=units[0]
    assert http.post('/api/reviews/units/'+first['id']+'/ratings',json={'request_id':str(uuid4()),'rating':1,'expected_state_version':1,'expected_content_revision':1},headers=csrf(http)).status_code==200
    assert http.get('/api/reviews/queue').json()['items']==[]
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        db.execute("UPDATE app.review_states SET due_at=now()-interval '1 minute' WHERE unit_id=%s",(first['id'],))
    assert http.get('/api/reviews/queue').json()['items'][0]['id']==first['id']
    active=card if card['id']==first['card']['id'] else second
    assert http.post('/api/cards/'+active['id']+'/lifecycle',json={'expected_revision':1,'action':'archive'},headers=csrf(http)).status_code==200
    assert http.get('/api/reviews/queue').json()['items']==[]


def test_concurrent_pins_and_collection_request_digest():
    http=account(); groups=[new_collection(http) for _ in range(7)]; headers=csrf(http)
    for group in groups[:5]:
        assert http.patch('/api/collections/'+group['id'],json={'expected_revision':1,'is_pinned':True},headers=headers).status_code==200
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda group:http.patch('/api/collections/'+group['id'],json={'expected_revision':1,'is_pinned':True},headers=headers).status_code,groups[5:]))
    assert sorted(statuses)==[200,409]
    assert len(http.get('/api/me/pinned-collections').json()['items'])==6
    payload={'client_request_id':str(uuid4()),'title':'幂等合集'}
    original=http.post('/api/collections',json=payload,headers=headers).json()
    edited=http.patch('/api/collections/'+original['id'],json={'expected_revision':1,'title':'修改后的合集'},headers=headers).json()
    assert http.post('/api/collections',json=payload,headers=headers).json()['title']==edited['title']
    assert http.post('/api/collections',json={**payload,'title':'另一个合集'},headers=headers).status_code==409


def test_atomic_creation_failure_manual_inline_and_restoration():
    http=account(); target,_=create(http); headers=csrf(http)
    # A missing relationship rolls back card, review unit and activity creation together.
    payload={'kind':'knowledge','form':'qa','title':'失败卡片','question_md':'问题','answer_md':'答案','client_request_id':str(uuid4()),'tag_ids':[str(uuid4())]}
    assert http.post('/api/cards',json=payload,headers=headers).status_code==404
    assert http.get('/api/cards').json()['total']==1
    opinion,_=create(http,'opinion',body_md='[['+target['id']+'|目标]]')
    manual=http.post('/api/cards/'+opinion['id']+'/links/'+target['id'],json={'expected_revision':1},headers=headers).json()
    assert http.request('DELETE','/api/cards/'+opinion['id']+'/links/'+target['id'],json={'expected_revision':manual['revision']},headers=headers).status_code==200
    assert http.get('/api/cards/'+opinion['id']+'/links').json()['outgoing'][0]['origins']==['inline']
    trash=http.post('/api/cards/'+target['id']+'/lifecycle',json={'expected_revision':1,'action':'trash'},headers=headers).json()
    assert http.get('/api/cards/'+opinion['id']+'/links').json()['outgoing'][0]['lifecycle']=='trashed'
    assert http.post('/api/cards/'+target['id']+'/lifecycle',json={'expected_revision':trash['revision'],'action':'restore'},headers=headers).status_code==200
    assert http.get('/api/cards/'+opinion['id']+'/links').json()['outgoing'][0]['lifecycle']=='active'


def test_timezone_calendar_streak_mastery_and_viewing_are_read_only():
    http=account(); card,_=create(http,form='cloze',question_md=None,answer_md=None,body_md='{{c1::一}} {{c2::二}}')
    owner=http.get('/api/auth/me').json()['id']; fixed=datetime(2026,10,4,16,30,tzinfo=timezone.utc)
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute('UPDATE app.activity_events SET occurred_at=%s WHERE owner_id=%s',(fixed,owner))
        heat=profiles.heatmap(db,owner,fixed)
        assert heat['days'][0]['date'].weekday()==0
        assert next(d['count'] for d in heat['days'] if d['date'].isoformat()=='2026-10-05')==1
        db.execute("UPDATE app.user_profiles SET timezone='UTC' WHERE user_id=%s",(owner,))
        heat=profiles.heatmap(db,owner,fixed)
        assert next(d['count'] for d in heat['days'] if d['date'].isoformat()=='2026-10-04')==1
        assert profiles.summary(db,owner,fixed)['streak']==1
        db.execute("UPDATE app.review_states SET state='review',last_reviewed_at=%s,due_at=%s WHERE owner_id=%s",(fixed,fixed+timedelta(days=22),owner))
    assert http.get('/api/reviews/summary').json()['mastered_cards']==1
    assert http.get('/api/me/summary').json()['knowledge']==1
    for _ in range(3): http.get('/api/cards/'+card['id']); http.get('/api/reviews/queue')
    assert http.get('/api/reviews/summary').json()['today_completed']==0
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        db.execute('UPDATE app.review_units SET is_active=false WHERE owner_id=%s',(owner,))
    assert http.get('/api/reviews/summary').json()['mastered_cards']==0


def test_rating_failure_rolls_back_state_log_and_activity(monkeypatch):
    http=account(); card,_=create(http)
    unit=http.get('/api/reviews/queue').json()['items'][0]
    def fail_event(*args,**kwargs): raise RuntimeError('injected activity failure')
    monkeypatch.setattr(reviews.cards,'event',fail_event)
    with pytest.raises(RuntimeError,match='injected'):
        http.post('/api/reviews/units/'+unit['id']+'/ratings',json={'request_id':str(uuid4()),'rating':3,'expected_state_version':1,'expected_content_revision':card['revision']},headers=csrf(http))
    queue=http.get('/api/reviews/queue').json()['items']
    assert queue[0]['state']=='new' and queue[0]['state_version']==1
    assert http.get('/api/reviews/summary').json()['today_completed']==0
    assert http.get('/api/me/activity').json()['total']==1


def test_admin_role_does_not_grant_access_to_member_content():
    member=account(); card,_=create(member); group=new_collection(member)
    create_first_admin('dev','127.0.0.1',6179,'keeper',PASSWORD)
    admin=TestClient(create_app()); assert login(admin,'keeper').status_code==200
    assert admin.get('/api/cards/'+card['id']).status_code==404
    assert admin.get('/api/collections/'+group['id']).status_code==404
    assert admin.get('/api/me/activity').json()['total']==0
    assert admin.get('/api/me/summary').json()['knowledge']==0


def test_identity_only_application_writes_remain_compatible_and_defaults_recover():
    owner=uuid4()
    # Mimic the previous application's user INSERT, which knew nothing about profile tables.
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        db.execute("INSERT INTO app.users(id,username,password_hash,role) VALUES(%s,'legacy',%s,'member')",(owner,hasher.hash(PASSWORD)))
        assert db.execute('SELECT count(*) FROM app.user_profiles WHERE user_id=%s',(owner,)).fetchone()==(0,)
    http=TestClient(create_app()); assert login(http,'legacy').status_code==200
    assert http.get('/api/auth/me').json()['username']=='legacy'
    assert http.get('/api/me/profile').json()['display_name']=='legacy'
    assert http.get('/api/me/summary').json()['knowledge']==0
