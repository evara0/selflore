"""Account-local tag identity, legacy partitions and shared filter predicates."""
import unicodedata
from uuid import uuid4
import psycopg
from app.repositories.workspace import one, many, run, fail


def normalize_name(value):
    value = unicodedata.normalize('NFKC', value).strip()
    if not 1 <= len(value) <= 80:
        raise ValueError('标签名称需为1至80字符')
    return value


def resolve(db, owner, entity, source='tag'):
    row = one(db, '''SELECT a.old_id AS id,a.canonical_tag_id AS tag_id,a.kind,t.name
        FROM app.tag_aliases a JOIN app.tags t ON t.owner_id=a.owner_id AND t.id=a.canonical_tag_id
        WHERE a.owner_id=%s AND a.source_type=%s AND a.old_id=%s''', (owner,source,entity))
    if not row and source == 'tag':
        row = one(db,'SELECT id,id AS tag_id,name,NULL::text AS kind FROM app.tags WHERE owner_id=%s AND id=%s',(owner,entity))
    if not row:
        fail(404,'not_found','对象不存在或不可用')
    return row


def listing(db, owner, source='tag', kind=None):
    if source == 'tag':
        return {'items': many(db, '''SELECT t.id,t.name,(SELECT count(*) FROM app.card_tags r JOIN app.cards c
            ON c.owner_id=r.owner_id AND c.id=r.card_id WHERE r.owner_id=t.owner_id AND r.tag_id=t.id AND c.lifecycle='active') AS card_count
            FROM app.tags t WHERE t.owner_id=%s ORDER BY t.name,t.id''',(owner,))}
    return {'items': many(db, '''SELECT a.old_id AS id,a.kind,a.canonical_tag_id AS tag_id,t.name,
        (SELECT count(*) FROM app.card_tags r JOIN app.cards c ON c.owner_id=r.owner_id AND c.id=r.card_id
         WHERE r.owner_id=t.owner_id AND r.tag_id=t.id AND c.kind=a.kind AND c.lifecycle='active') AS card_count
        FROM app.tag_aliases a JOIN app.tags t ON t.owner_id=a.owner_id AND t.id=a.canonical_tag_id
        WHERE a.owner_id=%s AND a.source_type='topic' '''+(' AND a.kind=%s' if kind else '')+' ORDER BY t.name,a.old_id',
        (owner,kind) if kind else (owner,))}


def write(db, owner, body, source='tag', entity=None):
    try:
        name=normalize_name(body.name)
    except ValueError as error:
        fail(422,'invalid_name',str(error))
    with db.transaction():
        if entity:
            target=resolve(db,owner,entity,source)
            tag_id=target['tag_id']
        else:
            target=None; tag_id=uuid4()
        existing=one(db,'SELECT id,name FROM app.tags WHERE owner_id=%s AND normalized_name=%s',(owner,name))
        if existing and (not target or existing['id']!=tag_id):
            if source!='topic' or entity:
                fail(409,'duplicate','标签已存在，可直接选用',existing_tag=existing)
            tag_id=existing['id']
            alias=one(db,"SELECT old_id AS id FROM app.tag_aliases WHERE owner_id=%s AND source_type='topic' AND kind=%s AND canonical_tag_id=%s ORDER BY old_id LIMIT 1",(owner,body.kind,tag_id))
            if alias:
                fail(409,'duplicate','分类名称已存在',existing_topic={'id':str(alias['id']),'name':name},existing_tag={'id':str(tag_id),'name':name})
        try:
            with db.transaction():
                if target:
                    run(db,'UPDATE app.tags SET name=%s WHERE owner_id=%s AND id=%s',(name,owner,tag_id))
                elif not existing:
                    run(db,'INSERT INTO app.tags(id,owner_id,name) VALUES(%s,%s,%s)',(tag_id,owner,name))
                if source=='topic' and not entity:
                    if not body.kind: fail(422,'missing_kind','请选择分类类型')
                    entity=uuid4()
                    run(db,'''INSERT INTO app.tag_aliases(owner_id,source_type,old_id,canonical_tag_id,kind,original_name,original_created_at)
                        VALUES(%s,'topic',%s,%s,%s,%s,now())''',(owner,entity,tag_id,body.kind,name))
        except psycopg.errors.UniqueViolation:
            existing=one(db,'SELECT id,name FROM app.tags WHERE owner_id=%s AND normalized_name=%s',(owner,name))
            fail(409,'duplicate','标签已存在，可直接选用',existing_tag=existing)
        return {'id':entity if source=='topic' else tag_id,'name':name,**({'kind':target['kind'] if target else body.kind,'tag_id':tag_id} if source=='topic' else {})}


def delete(db, owner, entity, source='tag'):
    with db.transaction():
        row=resolve(db,owner,entity,source)
        # Lock canonical object so a concurrent assignment cannot race deletion.
        one(db,'SELECT id FROM app.tags WHERE owner_id=%s AND id=%s FOR UPDATE',(owner,row['tag_id']))
        if one(db,'SELECT 1 FROM app.card_tags WHERE owner_id=%s AND tag_id=%s LIMIT 1',(owner,row['tag_id'])):
            fail(409,'in_use','仍被卡片使用，请先移除关联')
        run(db,'DELETE FROM app.tags WHERE owner_id=%s AND id=%s',(owner,row['tag_id']))


def sync(db, owner, card_id, data, changed=None):
    changed=set(changed) if changed is not None else {'topic_ids','tag_ids'}
    if data.taxonomy_mode=='unified':
        if 'tag_ids' not in changed: return
        updates={'unified':[(resolve(db,owner,i)['tag_id'],i) for i in data.tag_ids]}
        run(db,'DELETE FROM app.card_tag_sources WHERE owner_id=%s AND card_id=%s',(owner,card_id))
    else:
        updates={}
        for field,source,partition in (('topic_ids','topic','legacy_topic'),('tag_ids','tag','legacy_tag')):
            if field not in changed: continue
            pairs=[]
            for entity in getattr(data,field):
                target=resolve(db,owner,entity,source)
                if source=='topic' and target['kind']!=data.kind: fail(404,'not_found','对象不存在或不可用')
                pairs.append((target['tag_id'],entity))
            updates[partition]=pairs
            run(db,'DELETE FROM app.card_tag_sources WHERE owner_id=%s AND card_id=%s AND source_type=%s',(owner,card_id,partition))
    for partition,pairs in updates.items():
        for tag_id,source_id in pairs:
            run(db,'''INSERT INTO app.card_tag_sources(owner_id,card_id,tag_id,source_type,source_id)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(owner,card_id,tag_id,partition,source_id))
    count=one(db,'SELECT count(DISTINCT tag_id) AS n FROM app.card_tag_sources WHERE owner_id=%s AND card_id=%s',(owner,card_id))['n']
    if count>30: fail(422,'too_many_tags','每卡最多30个标签')
    run(db,'DELETE FROM app.card_tags WHERE owner_id=%s AND card_id=%s',(owner,card_id))
    run(db,'''INSERT INTO app.card_tags SELECT DISTINCT owner_id,card_id,tag_id FROM app.card_tag_sources
        WHERE owner_id=%s AND card_id=%s''',(owner,card_id))


def predicate(db, owner, ids=None, match='all', topic_id=None, tag_id=None):
    if ids is not None and (topic_id or tag_id): fail(422,'mixed_filters','不能混用新旧标签筛选')
    ids=list(dict.fromkeys(ids or []))
    if len(ids)>30: fail(422,'too_many_tags','最多筛选30个标签')
    if match not in ('all','any'): fail(422,'invalid_match','请选择全部或任一标签')
    conditions=[]; values=[]
    if topic_id:
        topic=resolve(db,owner,topic_id,'topic')
        conditions.append('c.kind=%s'); values.append(topic['kind'])
        ids.append(topic['tag_id'])
    if tag_id: ids.append(resolve(db,owner,tag_id)['tag_id'])
    ids=list(dict.fromkeys(resolve(db,owner,i)['tag_id'] for i in ids))
    if ids:
        if match=='all' or topic_id or tag_id:
            conditions.append('(SELECT count(*) FROM app.card_tags r WHERE r.owner_id=c.owner_id AND r.card_id=c.id AND r.tag_id=ANY(%s::uuid[]))=%s')
            values.extend([ids,len(ids)])
        else:
            conditions.append('EXISTS(SELECT 1 FROM app.card_tags r WHERE r.owner_id=c.owner_id AND r.card_id=c.id AND r.tag_id=ANY(%s::uuid[]))')
            values.append(ids)
    return (' AND '+' AND '.join(conditions) if conditions else ''),values
