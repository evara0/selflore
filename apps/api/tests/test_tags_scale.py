import json
import os
from pathlib import Path
from uuid import uuid4
import psycopg
from test_auth_integration import isolated_database
from test_workspace_integration import account
from test_unified_tags import tag
from app.services.tags import predicate


def test_multi_tag_scale_counts_pagination_and_plans():
    http=account(); owner=http.get('/api/auth/me').json()['id']
    a,b=tag(http,'AI'),tag(http,'LLM')
    with psycopg.connect(os.environ['SELFLORE_TEST_MIGRATOR_DSN']) as db:
        db.execute('SET LOCAL ROLE selflore_dev_owner')
        for n in range(1000):
            entity=uuid4()
            db.execute("INSERT INTO app.cards(id,owner_id,code,kind,title,body_md,search_text,client_request_id,creation_request_digest) VALUES(%s,%s,%s,'opinion','观点','正文','正文',%s,%s)",(entity,owner,str(n),uuid4(),'0'*64))
            for tag_id,divisor in [(a,2),(b,3)]:
                if n%divisor==0:
                    db.execute("INSERT INTO app.card_tag_sources VALUES(%s,%s,%s,'unified',%s)",(owner,entity,tag_id,tag_id))
                    db.execute('INSERT INTO app.card_tags VALUES(%s,%s,%s)',(owner,entity,tag_id))
        db.execute('ANALYZE app.card_tags'); db.execute('ANALYZE app.cards')
    plans={}
    for mode,total in [('all',167),('any',667)]:
        query=[('tag_ids',a),('tag_ids',b),('tag_match',mode),('limit','12')]
        first=http.get('/api/cards',params=query).json();again=http.get('/api/cards',params=query).json()
        second=http.get('/api/cards',params=query+[('offset','12')]).json()
        assert first['total']==second['total']==total
        assert [c['id'] for c in first['items']]==[c['id'] for c in again['items']]
        assert not ({c['id'] for c in first['items']}&{c['id'] for c in second['items']})
        with psycopg.connect(os.environ['SELFLORE_TEST_APP_DSN']) as db:
            where,values=predicate(db,owner,[a,b],mode)
            plans[mode]=db.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT c.id FROM app.cards c WHERE c.owner_id=%s AND c.lifecycle='active'"+where+' ORDER BY c.updated_at DESC,c.id DESC LIMIT 12',[owner,*values]).fetchone()[0]
    target=Path(__file__).resolve().parents[3]/'.cache/card-tests/tag-query-plans.json'
    target.write_text(json.dumps(plans,indent=2),encoding='utf-8')
