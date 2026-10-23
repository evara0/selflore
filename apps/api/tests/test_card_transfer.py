from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
from uuid import uuid4
import zipfile
import psycopg
import pytest
from PIL import Image
from app.media_storage import MediaConfig, initialize
from app.services import card_transfer
from app.services.card_package import Package
from test_workspace_integration import isolated_database, account
from test_auth_integration import csrf

EXAMPLE = Path(__file__).resolve().parents[3] / 'docs/card-transfer/example.json'


def post(http, action, raw, **data):
    return http.post('/api/card-transfer/'+action,files={'file':('cards.json',raw,'application/octet-stream')},data=data,headers=csrf(http))


def submit(http, raw, batch=None):
    preview=post(http,'validate',raw)
    assert preview.status_code==200,preview.text
    result=post(http,'import',raw,batch_id=batch or str(uuid4()),expected_digest=preview.json()['digest'])
    assert result.status_code==200,result.text
    return result.json()



def semantic(document):
    titles={c['key']:c['title'] for c in document['cards']}
    assets={a['key']:a['sha256'] for a in document['assets']}
    result=[]
    for raw in document['cards']:
        c=json.loads(json.dumps(raw))
        c.pop('key')
        for field in ('question_md','answer_md','body_md','note_md'):
            if c[field]:
                for key,title in titles.items():
                    c[field]=c[field].replace('[[card:'+key+'|','[[title:'+title+'|').replace('[[card:'+key+']]','[[title:'+title+']]')
        c['link_keys']=sorted(titles[k] for k in c['link_keys'])
        c['tags']=sorted(c['tags'])
        for item in c['memo_items']:
            item.pop('key')
            item['target_keys']=sorted(titles[k] for k in item['target_keys'])
            if item['completed_at']:item['completed_at']=datetime.fromisoformat(item['completed_at']).timestamp()
        for a in c['attachments']:a['asset_key']=assets[a['asset_key']]
        result.append(c)
    return sorted(result,key=lambda c:c['title'])


def test_json_roundtrip_and_retry():
    http=account(); raw=json.loads(EXAMPLE.read_bytes())
    raw['cards'][0]['answer_md']='答案 [[card:opinion|观点]]'
    raw['cards'][0]['lifecycle']='archived';raw['cards'][1]['lifecycle']='trashed'
    raw['cards'][5]['memo_items'][0].update(is_completed=True,completed_at='2025-01-02T03:04:05Z',target_keys=['reference'])
    content=json.dumps(raw).encode();batch=str(uuid4())
    preview=post(http,'validate',content).json()
    assert http.get('/api/cards',params={'kind':'memo'}).json()['total']==0
    result=submit(http,content,batch)
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        states=db.execute('SELECT state,review_count,last_reviewed_at FROM app.review_states WHERE owner_id=%s',(http.get('/api/auth/me').json()['id'],)).fetchall()
        assert len(states)==2 and all(row==('new',0,None) for row in states)
    assert submit(http,content,batch)==result
    changed_doc=json.loads(content);changed_doc['cards'][0]['title']='改动标题'
    changed=json.dumps(changed_doc).encode()
    conflict=post(http,'import',changed,batch_id=batch,expected_digest=post(http,'validate',changed).json()['digest'])
    assert conflict.status_code==409
    exported=http.get('/api/card-transfer/export?format=json')
    assert exported.status_code==200,exported.text
    assert 'no-store' in exported.headers['cache-control']
    assert len(exported.json()['cards'])==6
    target=account('bob'); imported=submit(target,exported.content)
    assert set(imported['mapping'].values()).isdisjoint(result['mapping'].values())
    restored=target.get('/api/card-transfer/export?format=json').json()
    assert semantic(exported.json())==semantic(restored)
    by_title={c['title']:c for c in restored['cards']}
    assert by_title['主动回忆']['lifecycle']=='archived'
    assert by_title['填空']['lifecycle']=='trashed'
    checklist=by_title['学习清单']
    assert checklist['memo_items'][0]['extra_values']==['明天','隐藏列仍保留']
    assert datetime.fromisoformat(checklist['memo_items'][0]['completed_at'])==datetime.fromisoformat('2025-01-02T03:04:05Z')
    assert len(checklist['memo_items'][0]['target_keys'])==1
    assert 'card:' in by_title['主动回忆']['answer_md']
    assert len(submit(http,exported.content)['mapping'])==6


def image_package():
    image=io.BytesIO();Image.new('RGB',(12,8),'red').save(image,format='PNG');data=image.getvalue()
    raw=json.loads(EXAMPLE.read_bytes())
    raw['assets']=[dict(key='image',path='media/image.png',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),mime_type='image/png')]
    raw['cards'][3]['attachments']=[dict(asset_key='image',caption='图注',alt_text='红图',creator_name='作者')]
    raw['cards'].append(dict(key='imageonly',kind='reference',title='共享图',attachments=[dict(asset_key='image')]))
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('manifest.json',json.dumps(raw).encode())
        archive.writestr('media/image.png',data)
    return output.getvalue(),data


@pytest.fixture
def media(monkeypatch,tmp_path):
    config=MediaConfig(tmp_path/'media',tmp_path/'ops','dev','selflore_dev')
    initialize(config)
    monkeypatch.setenv('SELFLORE_MEDIA_ROOT',str(config.root));monkeypatch.setenv('SELFLORE_MEDIA_OPS_ROOT',str(config.ops_root))
    return config


def test_zip_shared_image_roundtrip_and_missing_original(media):
    http=account();raw,data=image_package();first=submit(http,raw)
    assert len(first['asset_mapping'])==1
    assert http.get('/api/card-transfer/export?format=json').status_code==409
    exported=http.get('/api/card-transfer/export?format=zip')
    assert exported.status_code==200,exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert len(manifest['assets'])==1
        assert archive.read(manifest['assets'][0]['path'])==data
    target=account('bob')
    second=submit(target,exported.content)
    with zipfile.ZipFile(io.BytesIO(target.get('/api/card-transfer/export?format=zip').content)) as archive:
        assert semantic(manifest)==semantic(json.loads(archive.read('manifest.json')))
    assert second['asset_count']==1 and second['asset_mapping']!=first['asset_mapping']
    owner=http.get('/api/auth/me').json()['id']
    original=next((media.root/owner.replace('-','')).rglob('original.bin')); original.unlink()
    assert http.get('/api/card-transfer/export?format=zip').status_code==503


def test_import_transaction_rollback_and_retry(monkeypatch):
    http=account();raw=EXAMPLE.read_bytes();batch=str(uuid4())
    original=card_transfer.cards.event
    def broken(*args,**kwargs):
        raise RuntimeError('injected failure')
    monkeypatch.setattr(card_transfer.cards,'event',broken)
    with pytest.raises(RuntimeError):
        submit(http,raw,batch)
    assert http.get('/api/cards').json()['total']==0
    assert http.get('/api/tags').json()['items']==[]
    monkeypatch.setattr(card_transfer.cards,'event',original)
    assert submit(http,raw,batch)['card_count']==6


def test_security_invalid_content_and_preview_change():
    from fastapi.testclient import TestClient
    from app.main import create_app
    anonymous=TestClient(create_app())
    assert anonymous.get('/api/card-transfer/export').status_code==401
    assert anonymous.get('/api/card-transfer/schema').status_code==200
    http=account();raw=EXAMPLE.read_bytes()
    assert http.post('/api/card-transfer/validate',files={'file':('x',raw)}).status_code==403
    assert post(http,'import',raw,batch_id=str(uuid4()),expected_digest='0'*64).status_code==409
    invalid=json.loads(raw);invalid['cards'][-1]['memo_items'][0]['target_keys']=['missing']
    assert post(http,'import',json.dumps(invalid).encode(),batch_id=str(uuid4()),expected_digest='0'*64).status_code==422
    assert http.get('/api/cards').json()['total']==0


def test_more_than_one_page_and_empty_export():
    http=account()
    assert http.get('/api/card-transfer/export?format=json').json()['cards']==[]
    raw={'format':'selflore.cards','version':1,'cards':[dict(key=f'card{i}',kind='knowledge',form='qa',title=f'标题{i}',question_md='问',answer_md='完整答案') for i in range(105)]}
    submit(http,json.dumps(raw).encode())
    exported=http.get('/api/card-transfer/export?format=json').json()
    assert len(exported['cards'])==105
    assert all(c['answer_md']=='完整答案' for c in exported['cards'])

def test_parallel_retry_and_owner_isolation():
    http=account();raw=EXAMPLE.read_bytes();batch=uuid4()
    owner=http.get('/api/auth/me').json()['id']
    def execute(_):
        package=Package(io.BytesIO(raw))
        try:
            with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
                return card_transfer.import_package(db,owner,package,batch,package.digest)
        finally: package.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(execute,range(2)))
    assert results[0]==results[1]
    other=account('bob')
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        db.execute("UPDATE app.users SET role='admin' WHERE id=%s",(other.get('/api/auth/me').json()['id'],))
    assert other.get('/api/card-transfer/export?format=json').json()['cards']==[]
    independent=submit(other,raw,str(batch))
    assert set(independent['mapping'].values()).isdisjoint(results[0]['mapping'].values())
    assert other.get('/api/cards/'+next(iter(results[0]['mapping'].values()))).status_code==404


def test_media_publication_failure_recovery(media,monkeypatch):
    http=account();raw,_=image_package();batch=str(uuid4())
    original=card_transfer.shutil.copyfile
    def broken(*args,**kwargs):
        original(*args,**kwargs)
        raise OSError('simulated disk failure after partial publication')
    monkeypatch.setattr(card_transfer.shutil,'copyfile',broken)
    preview=post(http,'validate',raw).json()
    result=post(http,'import',raw,batch_id=batch,expected_digest=preview['digest'])
    assert result.status_code==503
    assert http.get('/api/cards').json()['total']==0
    assert len(list(media.ops_root.glob('transfer-*.json')))==1
    monkeypatch.setattr(card_transfer.shutil,'copyfile',original)
    assert submit(http,raw,batch)['asset_count']==1
    # Successful replay never removes ready originals.
    assert submit(http,raw,batch)['asset_count']==1
    assert len(list(media.root.rglob('original.bin')))==1


def test_package_budgets_and_corrupt_assets(media):
    http=account();raw,_=image_package()
    output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(output,'w') as target:
        for name in source.namelist():
            target.writestr(name,source.read(name) if name=='manifest.json' else b'bad')
    assert post(http,'validate',output.getvalue()).status_code==422
    excessive={'format':'selflore.cards','version':1,'cards':[dict(key=f'k{i}',kind='memo',memo_format='note',title='x') for i in range(2001)]}
    assert post(http,'validate',json.dumps(excessive).encode()).status_code==422


def test_import_batch_role_permissions():
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        assert db.execute("SELECT has_table_privilege(current_user,'app.card_import_batches','SELECT,INSERT')").fetchone()==(True,)
        assert db.execute("SELECT has_table_privilege(current_user,'app.card_import_batches','UPDATE')").fetchone()==(False,)
