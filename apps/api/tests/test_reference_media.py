import hashlib
import os
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.media_storage import MediaConfig,MARKER
from test_auth_integration import isolated_database,csrf
from test_workspace_integration import account,create,new_collection
from test_media_storage import configured,image_bytes


@pytest.fixture(autouse=True)
def media(tmp_path,monkeypatch):
    config=configured(tmp_path)
    monkeypatch.setenv('SELFLORE_MEDIA_ROOT',str(config.root))
    monkeypatch.setenv('SELFLORE_MEDIA_OPS_ROOT',str(config.ops_root))
    return config


def upload(http,content=None,request_id=None,digest=None):
    content=content if content is not None else image_bytes()
    return http.post('/api/attachments',files={'file':('picture.png',content,'image/png')},
                     data={'client_request_id':str(request_id or uuid4()),'file_sha256':digest or hashlib.sha256(content).hexdigest()},headers=csrf(http))


def reference(http,attachments=None,**fields):
    return http.post('/api/cards',json={'kind':'reference','title':'外部图表','attachments':attachments or [],
                     'client_request_id':str(uuid4()),**fields},headers=csrf(http))


def test_image_card_sources_search_review_and_lifecycle(media):
    http=account(); content=image_bytes(); response=upload(http,content); assert response.status_code==201,response.text
    image=response.json(); saved=reference(http,[{'id':image['id'],'caption':'示意图','creator_name':'图片作者'}],note_md='我收录的说明',source_author='原帖作者',source_publisher='转载者',source_platform='X')
    assert saved.status_code==201,saved.text
    card=saved.json(); assert card['kind']=='reference' and card['attachments'][0]['caption']=='示意图'
    assert http.get('/api/cards',params={'q':'原帖作者','kinds':'knowledge,reference'}).json()['total']==1
    assert http.get('/api/cards',params={'kind':'knowledge'}).json()['total']==0
    assert http.get('/api/cards',params={'kind':'knowledge','kinds':'reference'}).status_code==422
    assert http.get('/api/reviews/summary').json()['new_units']==0
    assert http.get('/api/me/summary').json()['references']==1
    raw=http.get(f"/api/attachments/{image['id']}/content?variant=original")
    assert raw.content==content and raw.headers['cache-control']=='private, no-store'
    assert http.get(f"/api/attachments/{image['id']}/content").headers['content-type']=='image/webp'
    group=new_collection(http)
    assert http.post(f"/api/collections/{group['id']}/items",json={'expected_revision':1,'card_ids':[card['id']]},headers=csrf(http)).status_code==200
    assert http.get(f"/api/collections/{group['id']}").json()['reference_count']==1
    assert http.get(f"/api/collections/{group['id']}/items").json()['items'][0]['attachments'][0]['id']==image['id']
    for action in ('trash','restore'):
        changed=http.post(f"/api/cards/{card['id']}/lifecycle",json={'expected_revision':card['revision'],'action':action},headers=csrf(http))
        assert changed.status_code==200; card=changed.json()
        assert http.get(f"/api/attachments/{image['id']}/content?variant=original").content==content


def test_idempotency_failure_isolation_and_conflict(media,monkeypatch):
    http=account(); request=uuid4(); image=upload(http,request_id=request).json()
    assert upload(http,request_id=request).json()['id']==image['id']
    assert upload(http,image_bytes(size=(21,31)),request_id=request).status_code==409
    assert upload(http,b'not an image').status_code==422
    monkeypatch.setenv('SELFLORE_MEDIA_MAX_BYTES','10')
    assert upload(http).status_code==413
    monkeypatch.delenv('SELFLORE_MEDIA_MAX_BYTES')
    bob=account('bob')
    for suffix in ('','/content','/content?variant=original'):
        assert bob.get('/api/attachments/'+image['id']+suffix).status_code==404
    assert reference(bob,[{'id':image['id']}]).status_code==404
    assert TestClient(create_app()).get('/api/attachments/'+image['id']+'/content').status_code==401
    saved=reference(http,[{'id':image['id']}]).json()
    patch={'expected_revision':saved['revision'],'attachments':[{'id':image['id'],'caption':'更新'}]}
    assert http.patch('/api/cards/'+saved['id'],json=patch,headers=csrf(http)).status_code==200
    assert http.patch('/api/cards/'+saved['id'],json=patch,headers=csrf(http)).status_code==409
    assert reference(http,note_md='仅说明').status_code==422
    assert reference(http,body_md='外部摘录').status_code==201


def test_concurrent_retry_and_interrupted_recovery(media):
    http=account(); request=uuid4(); headers=csrf(http); content=image_bytes()
    def send():
        return http.post('/api/attachments',files={'file':('p',content)},data={'client_request_id':str(request),'file_sha256':hashlib.sha256(content).hexdigest()},headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool: responses=list(pool.map(lambda _:send(),range(2)))
    assert all(r.status_code in (201,409) for r in responses)
    ready=send(); assert ready.status_code==201
    owner=http.get('/api/auth/me').json()['id']; interrupted=uuid4()
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute("INSERT INTO app.attachments(id,owner_id,status,client_request_id,request_sha256) VALUES(%s,%s,'uploading',%s,%s)",(uuid4(),owner,interrupted,hashlib.sha256(content).hexdigest()))
    assert upload(http,request_id=interrupted).status_code==201


def test_direct_database_enforces_final_material_and_ready(media):
    http=account(); image=upload(http).json(); owner=http.get('/api/auth/me').json()['id']
    card=reference(http,[{'id':image['id']}]).json()
    dsn=os.environ['SELFLORE_TEST_MIGRATOR_DSN']
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(dsn) as db:
            db.execute('SET LOCAL ROLE selflore_dev_owner')
            db.execute('DELETE FROM app.card_attachments WHERE card_id=%s',(card['id'],))
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(dsn) as db:
            db.execute('SET LOCAL ROLE selflore_dev_owner')
            db.execute("UPDATE app.attachments SET status='failed' WHERE id=%s",(image['id'],))
    assert http.get('/api/cards/'+card['id']).json()['attachments']


def test_storage_and_thumbnail_failures_never_publish_ready(media,monkeypatch):
    from app.services import attachments
    http=account()
    monkeypatch.setattr(attachments,'image_thumbnail',lambda *args: (_ for _ in ()).throw(OSError('synthetic disk failure')))
    assert upload(http).status_code==503
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        assert db.execute("SELECT count(*) FROM app.attachments WHERE status='ready'").fetchone()[0]==0
    monkeypatch.delenv('SELFLORE_MEDIA_ROOT')
    assert upload(http).status_code==503
    assert http.get('/api/health').json()=={'ok':True}


def test_database_failure_after_file_publication_is_reported(media,monkeypatch):
    from app.services import attachments
    http=account(); original_one=attachments.one
    def fail_ready(db,query,args=()):
        if query.startswith("UPDATE app.attachments SET status='ready'"):
            raise psycopg.OperationalError('synthetic commit path failure')
        return original_one(db,query,args)
    monkeypatch.setattr(attachments,'one',fail_ready)
    assert upload(http).status_code==503
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        assert db.execute("SELECT count(*) FROM app.attachments WHERE status='ready'").fetchone()[0]==0
    assert list(media.root.rglob('original.bin'))  # Published immutable file retained for diagnosis.


def test_sql_wrong_card_cross_owner_and_pending_attachment(media):
    http=account(); other=account('bob'); image=upload(http).json(); other_image=upload(other).json()
    card=reference(http,[{'id':image['id']}]).json(); knowledge,_=create(http)
    owner=http.get('/api/auth/me').json()['id']; dsn=os.environ['SELFLORE_TEST_MIGRATOR_DSN']
    def execute(query,args,exception):
        with pytest.raises(exception):
            with psycopg.connect(dsn) as db:
                db.execute('SET LOCAL ROLE selflore_dev_owner'); db.execute(query,args)
    insert='INSERT INTO app.card_attachments(owner_id,card_id,attachment_id,position) VALUES(%s,%s,%s,1)'
    execute(insert,(owner,card['id'],other_image['id']),psycopg.errors.ForeignKeyViolation)
    execute(insert,(owner,knowledge['id'],image['id']),psycopg.errors.ForeignKeyViolation)
    pending=uuid4()
    with psycopg.connect(dsn) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute("INSERT INTO app.attachments(id,owner_id,status,client_request_id,request_sha256) VALUES(%s,%s,'uploading',%s,%s)",(pending,owner,uuid4(),'0'*64))
    execute(insert,(owner,card['id'],pending),psycopg.errors.CheckViolation)
    second=upload(http,image_bytes(size=(25,25))).json()
    execute(insert.replace(',1)',',0)'),(owner,card['id'],second['id']),psycopg.errors.UniqueViolation)


def test_diagnostics_cli_readonly_explicit_record_and_bad_identity(media,capsys):
    from app.media_diagnostics import main
    http=account(); image=upload(http).json(); reference(http,[{'id':image['id']}],note_md='private-note-not-in-report')
    before=set(media.root.rglob('*')); ops_before=set(media.ops_root.iterdir())
    assert main(['--expected-port','6179','--json'])==1
    output=capsys.readouterr().out
    assert 'private-note-not-in-report' not in output and 'growth_unknown' in output
    assert before==set(media.root.rglob('*')) and ops_before==set(media.ops_root.iterdir())
    assert main(['--expected-port','6179','--record','--output','report.json'])==1
    assert (media.ops_root/'capacity.jsonl').is_file() and (media.ops_root/'report.json').is_file()
    assert main(['--expected-port','6171','--json'])==3
    assert main(['--expected-port','6179','--output','../escape.json','--json'])==3
    assert not (media.ops_root.parent/'escape.json').exists()


def test_legacy_creation_retry_after_upgrade_keeps_identity_and_rejects_new_content(media):
    from app.schemas.workspace import CardCreate
    from app.services.cards import digest
    http=account(); card,payload=create(http)
    normalized=CardCreate.model_validate(payload).model_dump(mode='json')
    for key in ('note_md','attachments','source_author','source_publisher','source_platform','source_published_on'):
        normalized.pop(key)
    legacy_digest=digest(normalized)
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute('UPDATE app.cards SET creation_request_digest=%s WHERE id=%s',(legacy_digest,card['id']))
    retry=http.post('/api/cards',json=payload,headers=csrf(http))
    assert retry.status_code==201 and retry.json()['id']==card['id']
    assert http.post('/api/cards',json={**payload,'source_author':'new author'},headers=csrf(http)).status_code==409
    assert http.get('/api/cards').json()['total']==1
