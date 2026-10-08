import json
import os
from pathlib import Path
from uuid import uuid4
import psycopg
from test_auth_integration import isolated_database
from test_workspace_integration import account
from app.services.cards import SELECT


def test_thousand_card_chinese_search_and_plan():
    http=account(); owner=http.get('/api/auth/me').json()['id']
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        rows=[(uuid4(),owner,'K-'+str(i),'知识与记忆 '+str(i%20),'主动回忆的意义','检索记忆','知识与记忆 '+str(i),uuid4(),'0'*64) for i in range(1000)]
        with db.cursor() as cursor:
            cursor.executemany("INSERT INTO app.cards(id,owner_id,code,title,question_md,answer_md,search_text,client_request_id,creation_request_digest,kind,form) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'knowledge','qa')",rows)
        db.execute('ANALYZE app.cards')
    response=http.get('/api/cards',params={'kind':'knowledge','q':'忆','limit':12}).json()
    assert response['total']==1000 and len(response['items'])==12
    again=http.get('/api/cards',params={'kind':'knowledge','q':'忆','limit':12}).json()
    assert [r['id'] for r in response['items']]==[r['id'] for r in again['items']]
    with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
        plan=db.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+SELECT+" WHERE c.owner_id=%s AND c.kind='knowledge' AND c.lifecycle='active' AND c.search_text ILIKE %s ORDER BY c.updated_at DESC,c.id DESC LIMIT 12",(owner,'%忆%')).fetchone()[0]
    target=Path(__file__).resolve().parents[3]/'docs'/'design'/'card-navigation-v1'/'implemented'/'search-explain.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
