from __future__ import annotations

from uuid import uuid4
import psycopg
from pydantic import ValidationError

from app.repositories.workspace import one, many, run, owned, revision, fail
from app.schemas.workspace import CollectionContent
from app.services.cards import digest, event, change_lifecycle

SELECT="""SELECT c.*,
 (SELECT count(*) FROM app.collection_items i WHERE i.owner_id=c.owner_id AND i.collection_id=c.id) AS total_items,
 (SELECT count(*) FROM app.collection_items i JOIN app.cards x ON x.owner_id=i.owner_id AND x.id=i.card_id
  WHERE i.owner_id=c.owner_id AND i.collection_id=c.id AND x.lifecycle='active') AS available_items,
 (SELECT count(*) FROM app.collection_items i JOIN app.cards x ON x.owner_id=i.owner_id AND x.id=i.card_id
  WHERE i.owner_id=c.owner_id AND i.collection_id=c.id AND x.kind='knowledge') AS knowledge_count,
 (SELECT count(*) FROM app.collection_items i JOIN app.cards x ON x.owner_id=i.owner_id AND x.id=i.card_id
  WHERE i.owner_id=c.owner_id AND i.collection_id=c.id AND x.kind='opinion') AS opinion_count
 FROM app.collections c"""


def public(row):
    return {k:v for k,v in row.items() if k not in {'owner_id','creation_request_digest','client_request_id'}}


def detail(db,owner,entity):
    row=one(db,SELECT+' WHERE c.owner_id=%s AND c.id=%s',(owner,entity))
    if not row: fail(404,'not_found','对象不存在或不可用')
    return public(row)


def listing(db,owner,q=None,is_favorite=None,lifecycle='active',limit=24,offset=0):
    where=' WHERE c.owner_id=%s AND c.lifecycle=%s'; args=[owner,lifecycle]
    if q:
        where+=' AND c.title ILIKE %s'; args.append('%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
    if is_favorite is not None:
        where+=' AND c.is_favorite=%s'; args.append(is_favorite)
    total=one(db,'SELECT count(*) AS n FROM app.collections c'+where,args)['n']
    rows=many(db,SELECT+where+' ORDER BY c.updated_at DESC,c.id DESC LIMIT %s OFFSET %s',(*args,limit,offset))
    return {'items':[public(row) for row in rows],'total':total,'limit':limit,'offset':offset}


def pin_guard(db,owner,entity=None):
    one(db,'SELECT user_id FROM app.user_profiles WHERE user_id=%s FOR UPDATE',(owner,))
    n=one(db,"SELECT count(*) AS n FROM app.collections WHERE owner_id=%s AND is_pinned AND lifecycle='active' AND (%s::uuid IS NULL OR id<>%s)",(owner,entity,entity))['n']
    if n>=6: fail(409,'pin_limit','最多置顶 6 个合集')


def create(db,owner,data):
    fingerprint=digest(data.model_dump(mode='json'))
    old=one(db,'SELECT id,creation_request_digest FROM app.collections WHERE owner_id=%s AND client_request_id=%s',(owner,data.client_request_id))
    if old:
        if old['creation_request_digest']!=fingerprint: fail(409,'request_conflict','请求标识已用于不同内容')
        return detail(db,owner,old['id'])
    entity=uuid4(); values=data.model_dump(exclude={'client_request_id'})
    try:
        with db.transaction():
            if data.is_pinned: pin_guard(db,owner)
            keys=['id','owner_id','client_request_id','creation_request_digest',*values]
            args=[entity,owner,data.client_request_id,fingerprint,*values.values()]
            run(db,'INSERT INTO app.collections('+','.join(keys)+') VALUES('+','.join(['%s']*len(args))+')',args)
            event(db,owner,'collection_created',{'id':entity,'title':data.title},collection=True)
    except psycopg.errors.UniqueViolation:
        old=one(db,'SELECT id,creation_request_digest FROM app.collections WHERE owner_id=%s AND client_request_id=%s',(owner,data.client_request_id))
        if not old or old['creation_request_digest']!=fingerprint: fail(409,'request_conflict','创建请求冲突')
        entity=old['id']
    return detail(db,owner,entity)


def edit(db,owner,entity,patch):
    with db.transaction():
        if patch.is_pinned: pin_guard(db,owner,entity)
        row=owned(db,'collections',owner,entity,lock=True); revision(row,patch.expected_revision)
        values={k:row[k] for k in CollectionContent.model_fields}
        values.update(patch.model_dump(exclude_unset=True,exclude={'expected_revision'}))
        try: values=CollectionContent.model_validate(values).model_dump()
        except ValidationError: fail(422,'invalid_content','请检查合集标题和说明')
        run(db,'UPDATE app.collections SET '+','.join(k+'=%s' for k in values)+',revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',(*values.values(),owner,entity))
        event(db,owner,'collection_updated',{'id':entity,'title':values['title']},collection=True)
    return detail(db,owner,entity)


def lifecycle(db,owner,entity,body):
    with db.transaction():
        old=owned(db,'collections',owner,entity)
        if body.action=='restore' and old['is_pinned']: pin_guard(db,owner,entity)
        change_lifecycle(db,'collections',owner,entity,body.action,body.expected_revision)
    return detail(db,owner,entity)


def items(db,owner,entity):
    parent=owned(db,'collections',owner,entity)
    rows=many(db,"""SELECT i.id AS item_id,i.position,c.id,c.title,c.kind,c.form,c.code,c.lifecycle,c.revision,
      CASE WHEN c.lifecycle='active' AND %s='active' THEN c.question_md END AS question_md,
      CASE WHEN c.lifecycle='active' AND %s='active' THEN c.answer_md END AS answer_md,
      CASE WHEN c.lifecycle='active' AND %s='active' THEN c.body_md END AS body_md
      FROM app.collection_items i JOIN app.cards c ON c.owner_id=i.owner_id AND c.id=i.card_id
      WHERE i.owner_id=%s AND i.collection_id=%s ORDER BY i.position""",(parent['lifecycle'],)*3+(owner,entity))
    return {'items':rows,'revision':parent['revision']}


def update_items(db,owner,entity,expected,*,add=None,remove=None,order=None):
    with db.transaction():
        row=owned(db,'collections',owner,entity,lock=True); revision(row,expected)
        if row['lifecycle']!='active': fail(409,'unavailable','请先恢复合集')
        current=many(db,'SELECT * FROM app.collection_items WHERE owner_id=%s AND collection_id=%s ORDER BY position',(owner,entity))
        if add is not None:
            if len(set(add))!=len(add): fail(422,'duplicate','卡片不能重复')
            if len(many(db,"SELECT id FROM app.cards WHERE owner_id=%s AND id=ANY(%s::uuid[]) AND lifecycle='active'",(owner,add)))!=len(add): fail(404,'not_found','卡片不存在或不可用')
            if set(add)&{r['card_id'] for r in current}: fail(409,'duplicate','卡片已在此合集中')
            for card_id in add:
                item={'id':uuid4(),'card_id':card_id,'position':len(current)}
                run(db,'INSERT INTO app.collection_items(id,owner_id,collection_id,card_id,position) VALUES(%s,%s,%s,%s,%s)',(item['id'],owner,entity,card_id,item['position']))
                current.append(item)
        if remove is not None:
            if remove not in {r['id'] for r in current}: fail(404,'not_found','成员不存在或不可用')
            run(db,'DELETE FROM app.collection_items WHERE owner_id=%s AND collection_id=%s AND id=%s',(owner,entity,remove))
            current=[r for r in current if r['id']!=remove]
        ids=order if order is not None else [r['id'] for r in current]
        if len(ids)!=len(set(ids)) or set(ids)!={r['id'] for r in current}: fail(422,'invalid_order','排序需包含每个成员恰好一次')
        for position,item_id in enumerate(ids):
            run(db,'UPDATE app.collection_items SET position=%s WHERE owner_id=%s AND collection_id=%s AND id=%s',(position,owner,entity,item_id))
        run(db,'UPDATE app.collections SET revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',(owner,entity))
        event(db,owner,'collection_updated',row,collection=True)
    return detail(db,owner,entity)
