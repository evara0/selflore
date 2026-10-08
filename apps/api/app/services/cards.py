from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from app.repositories.workspace import one, many, run, owned, revision, fail
from app.schemas.workspace import CardContent
from app.services.content import references, cloze_indices
from app.services.scheduling import fresh, VERSION

FIELDS = ('kind','form','title','question_md','answer_md','body_md','source_title','source_url','source_locator','processing_state','is_bookmarked')
SELECT = """SELECT c.*,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('id',t.id,'name',t.name) ORDER BY t.name)
      FROM app.card_tags ct JOIN app.tags t ON t.owner_id=ct.owner_id AND t.id=ct.tag_id
      WHERE ct.owner_id=c.owner_id AND ct.card_id=c.id),'[]'::jsonb) AS tags,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('id',t.id,'name',t.name) ORDER BY t.name)
      FROM app.card_topics ct JOIN app.topics t ON t.owner_id=ct.owner_id AND t.id=ct.topic_id
      WHERE ct.owner_id=c.owner_id AND ct.card_id=c.id),'[]'::jsonb) AS topics,
    (SELECT count(DISTINCT target_card_id) FROM app.card_links l WHERE l.owner_id=c.owner_id AND l.source_card_id=c.id) AS link_count,
    (SELECT count(DISTINCT source_card_id) FROM app.card_links l WHERE l.owner_id=c.owner_id AND l.target_card_id=c.id) AS backlink_count
    FROM app.cards c"""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False, separators=(',',':')).encode()).hexdigest()


def event(db, owner, kind, row, *, collection=False, now=None):
    run(db, 'INSERT INTO app.activity_events(id,owner_id,card_id,collection_id,event_kind,entity_title,occurred_at) VALUES(%s,%s,%s,%s,%s,%s,%s)',
        (uuid4(),owner,None if collection else row['id'],row['id'] if collection else None,kind,row['title'],now or datetime.now(timezone.utc)))


def search_text(row, code):
    return '\n'.join(str(row.get(key) or '') for key in ('title','question_md','answer_md','body_md','source_title','source_locator')) + '\n' + code


def public(row, *, summary=False):
    result = dict(row)
    for key in ('owner_id','creation_request_digest','client_request_id','search_text'):
        result.pop(key, None)
    result['topic_ids'] = [t['id'] for t in result.get('topics',[])]
    result['tag_ids'] = [t['id'] for t in result.get('tags',[])]
    text = result.get('body_md') or result.get('question_md') or ''
    if result['kind']=='knowledge' and result['form']=='cloze':
        from app.services.content import cloze_text
        text=cloze_text(text,None,False)
    text=re.sub(r'\[\[([0-9a-f-]{36})(?:\|([^\]]*))?\]\]',lambda m:m[2] or '关联卡片',text,flags=re.I)
    result['excerpt'] = re.sub(r'\s+', ' ', re.sub(r'[#*_>`]', '', text))[:180]
    if summary:
        result.pop('answer_md',None)
        result.pop('body_md',None)
    return result


def detail(db, owner, card_id):
    row = one(db, SELECT+' WHERE c.owner_id=%s AND c.id=%s', (owner,card_id))
    if row is None:
        fail(404,'not_found','对象不存在或不可用')
    return public(row)


def list_cards(db, owner, *, kind=None, q=None, topic_id=None, tag_id=None, lifecycle='active', processing_state=None, is_bookmarked=None, sort='updated_desc', limit=24, offset=0):
    conditions, values = ['c.owner_id=%s','c.lifecycle=%s'], [owner,lifecycle]
    for key,value in (('kind',kind),('processing_state',processing_state),('is_bookmarked',is_bookmarked)):
        if value is not None:
            conditions.append(f'c.{key}=%s'); values.append(value)
    if q:
        conditions.append("c.search_text ILIKE %s ESCAPE '\\'")
        values.append('%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
    for table,field,value in (('card_topics','topic_id',topic_id),('card_tags','tag_id',tag_id)):
        if value is not None:
            conditions.append(f'EXISTS(SELECT 1 FROM app.{table} r WHERE r.owner_id=c.owner_id AND r.card_id=c.id AND r.{field}=%s)')
            values.append(value)
    where = ' WHERE '+' AND '.join(conditions)
    orders = {'updated_desc':'c.updated_at DESC,c.id DESC','created_desc':'c.created_at DESC,c.id DESC','code_asc':'c.code,c.id',
              'connections_desc':'link_count+backlink_count DESC,c.updated_at DESC,c.id DESC'}
    # Alias expressions cannot be combined in ORDER BY; use an outer query for connection sort.
    order = orders[sort]
    query = SELECT+where
    if sort=='connections_desc':
        query='SELECT * FROM ('+query+') c'
    total=one(db,'SELECT count(*) AS n FROM app.cards c'+where,values)['n']
    rows=many(db,query+' ORDER BY '+order+' LIMIT %s OFFSET %s',(*values,limit,offset))
    return {'items':[public(row,summary=True) for row in rows],'total':total,'limit':limit,'offset':offset}


def relations(db, owner, card_id, data):
    for ids,table in ((data.topic_ids,'topics'),(data.tag_ids,'tags')):
        if ids:
            extra=' AND kind=%s' if table=='topics' else ''
            values=(owner,ids,data.kind) if table=='topics' else (owner,ids)
            found=many(db,f'SELECT id FROM app.{table} WHERE owner_id=%s AND id=ANY(%s::uuid[])'+extra,values)
            if len(found)!=len(ids):
                fail(404,'not_found','分类或标签不存在或不可用')
    for table,key,ids in (('card_topics','topic_id',data.topic_ids),('card_tags','tag_id',data.tag_ids)):
        run(db,f'DELETE FROM app.{table} WHERE owner_id=%s AND card_id=%s',(owner,card_id))
        for entity_id in ids:
            if table=='card_topics':
                run(db,'INSERT INTO app.card_topics(owner_id,card_id,topic_id,card_kind) VALUES(%s,%s,%s,%s)',(owner,card_id,entity_id,data.kind))
            else:
                run(db,'INSERT INTO app.card_tags(owner_id,card_id,tag_id) VALUES(%s,%s,%s)',(owner,card_id,entity_id))
    try:
        targets=references('\n'.join(value or '' for value in (data.body_md,data.question_md,data.answer_md)))
    except ValueError as error:
        fail(422,'invalid_reference',str(error))
    if card_id in targets:
        fail(422,'self_link','不能链接卡片自身')
    if targets and len(many(db,'SELECT id FROM app.cards WHERE owner_id=%s AND id=ANY(%s::uuid[])',(owner,list(targets))))!=len(targets):
        fail(404,'not_found','引用目标不存在或不可用')
    run(db,"DELETE FROM app.card_links WHERE owner_id=%s AND source_card_id=%s AND origin='inline'",(owner,card_id))
    for target in targets:
        run(db,"INSERT INTO app.card_links(owner_id,source_card_id,target_card_id,origin) VALUES(%s,%s,%s,'inline')",(owner,card_id,target))


def sync_units(db,owner,card_id,data):
    if data.kind!='knowledge':
        return
    indices=[0] if data.form=='qa' else cloze_indices(data.body_md)
    units=many(db,'SELECT * FROM app.review_units WHERE owner_id=%s AND card_id=%s ORDER BY id FOR UPDATE',(owner,card_id))
    existing={row['cloze_index']:row for row in units}
    now=datetime.now(timezone.utc)
    for index in indices:
        old=existing.get(index)
        if old and old['is_active']:
            continue
        unit_id=old['id'] if old else uuid4()
        if old:
            run(db,'UPDATE app.review_units SET is_active=true,updated_at=now() WHERE owner_id=%s AND id=%s',(owner,unit_id))
            run(db,"UPDATE app.review_states SET state='new',due_at=%s,last_reviewed_at=NULL,review_count=0,lapse_count=0,scheduler_payload=%s,scheduler_version=%s,version=version+1 WHERE owner_id=%s AND unit_id=%s",
                (now,Jsonb(fresh(now)),VERSION,owner,unit_id))
        else:
            run(db,'INSERT INTO app.review_units(id,owner_id,card_id,cloze_index) VALUES(%s,%s,%s,%s)',(unit_id,owner,card_id,index))
            run(db,'INSERT INTO app.review_states(owner_id,unit_id,due_at,scheduler_payload,scheduler_version) VALUES(%s,%s,%s,%s,%s)',(owner,unit_id,now,Jsonb(fresh(now)),VERSION))
    run(db,'UPDATE app.review_units SET is_active=false,updated_at=now() WHERE owner_id=%s AND card_id=%s AND NOT(cloze_index=ANY(%s::smallint[]))',(owner,card_id,indices))


def create_card(db,owner,data):
    values=data.model_dump(); fingerprint=digest(data.model_dump(mode='json'))
    old=one(db,'SELECT id,creation_request_digest FROM app.cards WHERE owner_id=%s AND client_request_id=%s',(owner,data.client_request_id))
    if old:
        if old['creation_request_digest']!=fingerprint: fail(409,'request_conflict','请求标识已用于不同内容')
        return detail(db,owner,old['id'])
    entity_id=uuid4(); code=datetime.now(timezone.utc).strftime('%Y%m%d')+'-'+entity_id.hex.upper()
    try:
        with db.transaction():
            columns=('id','owner_id','code',*FIELDS,'search_text','client_request_id','creation_request_digest')
            params=(entity_id,owner,code,*(values[key] for key in FIELDS),search_text(values,code),data.client_request_id,fingerprint)
            run(db,'INSERT INTO app.cards('+','.join(columns)+') VALUES('+','.join(['%s']*len(params))+')',params)
            relations(db,owner,entity_id,data); sync_units(db,owner,entity_id,data)
            event(db,owner,'card_created',{'id':entity_id,'title':data.title})
    except psycopg.errors.UniqueViolation:
        old=one(db,'SELECT id,creation_request_digest FROM app.cards WHERE owner_id=%s AND client_request_id=%s',(owner,data.client_request_id))
        if not old or old['creation_request_digest']!=fingerprint: fail(409,'request_conflict','创建请求冲突，请重试')
        entity_id=old['id']
    return detail(db,owner,entity_id)


def edit_card(db,owner,card_id,patch):
    with db.transaction():
        row=owned(db,'cards',owner,card_id,lock=True); revision(row,patch.expected_revision)
        before=detail(db,owner,card_id)
        payload={key:before[key] for key in CardContent.model_fields if key in before}
        original=CardContent.model_validate(payload).model_dump(mode='json')
        payload.update(patch.model_dump(exclude_unset=True,exclude={'expected_revision'}))
        try:
            data=CardContent.model_validate(payload)
        except (ValidationError,ValueError):
            fail(422,'invalid_content','请检查问题、答案、正文和分类标签')
        values=data.model_dump()
        if original==data.model_dump(mode='json'):
            return before
        run(db,'UPDATE app.cards SET '+','.join(key+'=%s' for key in FIELDS)+',search_text=%s,revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',
            (*(values[key] for key in FIELDS),search_text(values,row['code']),owner,card_id))
        relations(db,owner,card_id,data); sync_units(db,owner,card_id,data)
        content_changed=any(before.get(k)!=values.get(k) for k in ('body_md','question_md','answer_md'))
        event(db,owner,'card_updated' if content_changed else 'card_organized',{'id':card_id,'title':data.title})
    return detail(db,owner,card_id)


def change_lifecycle(db,table,owner,entity,action,expected):
    with db.transaction():
        row=owned(db,table,owner,entity,lock=True); revision(row,expected)
        if table=='collections' and action=='archive': fail(422,'invalid_action','合集不支持归档')
        target={'archive':'archived','trash':'trashed','restore':'active'}[action]
        run(db,f'UPDATE app.{table} SET lifecycle=%s,trashed_at=%s,revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',
            (target,datetime.now(timezone.utc) if target=='trashed' else None,owner,entity))
    return detail(db,owner,entity) if table=='cards' else owned(db,table,owner,entity)


def link_list(db,owner,card_id):
    owned(db,'cards',owner,card_id)
    def fetch(direction):
        field,other=('source_card_id','target_card_id') if direction=='outgoing' else ('target_card_id','source_card_id')
        rows=many(db,f'''SELECT c.id,c.title,c.kind,c.code,c.lifecycle,array_agg(DISTINCT l.origin) AS origins
          FROM app.card_links l JOIN app.cards c ON c.owner_id=l.owner_id AND c.id=l.{other}
          WHERE l.owner_id=%s AND l.{field}=%s GROUP BY c.id ORDER BY c.title''',(owner,card_id))
        return rows
    return {'outgoing':fetch('outgoing'),'incoming':fetch('incoming')}


def manual_link(db,owner,card_id,target,expected,remove=False):
    with db.transaction():
        row=owned(db,'cards',owner,card_id,lock=True); revision(row,expected)
        owned(db,'cards',owner,target)
        if card_id==target: fail(422,'self_link','不能链接卡片自身')
        if remove:
            run(db,"DELETE FROM app.card_links WHERE owner_id=%s AND source_card_id=%s AND target_card_id=%s AND origin='manual'",(owner,card_id,target))
        else:
            run(db,"INSERT INTO app.card_links(owner_id,source_card_id,target_card_id,origin) VALUES(%s,%s,%s,'manual') ON CONFLICT DO NOTHING",(owner,card_id,target))
        run(db,'UPDATE app.cards SET revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',(owner,card_id))
        event(db,owner,'card_organized',row)
    return detail(db,owner,card_id)
