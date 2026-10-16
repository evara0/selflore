from datetime import datetime, timezone

from app.repositories.workspace import many, one, run, owned, revision, fail


def items(db, owner, card_id):
    rows = many(db, '''SELECT id,text,is_completed,completed_at FROM app.memo_items
        WHERE owner_id=%s AND memo_card_id=%s ORDER BY position''', (owner,card_id))
    for row in rows:
        row['targets'] = many(db, '''SELECT c.id,c.title,c.kind,c.lifecycle FROM app.memo_item_links l
            JOIN app.cards c ON c.owner_id=l.owner_id AND c.id=l.target_card_id
            WHERE l.owner_id=%s AND l.item_id=%s ORDER BY c.title,c.id''', (owner,row['id']))
        row['target_ids'] = [target['id'] for target in row['targets']]
    return rows


def inputs(rows):
    return [{key: row[key] for key in ('id','text','is_completed','target_ids')} for row in rows]


def sync(db, owner, card_id, data):
    if data.kind != 'memo':
        return
    old = {row['id']: row for row in many(db, 'SELECT * FROM app.memo_items WHERE owner_id=%s AND memo_card_id=%s', (owner,card_id))}
    ids = [item.id for item in data.memo_items]
    if ids and many(db, 'SELECT id FROM app.memo_items WHERE id=ANY(%s::uuid[]) AND (owner_id<>%s OR memo_card_id<>%s)', (ids,owner,card_id)):
        fail(404,'not_found','条目不存在或不可用')
    targets = set(target for item in data.memo_items for target in item.target_ids)
    if card_id in targets:
        fail(422,'self_link','不能关联所属清单自身')
    if targets and len(many(db,'SELECT id FROM app.cards WHERE owner_id=%s AND id=ANY(%s::uuid[])',(owner,list(targets)))) != len(targets):
        fail(404,'not_found','关联不存在或不可用')
    run(db,'DELETE FROM app.memo_items WHERE owner_id=%s AND memo_card_id=%s AND NOT(id=ANY(%s::uuid[]))',(owner,card_id,ids))
    for position, item in enumerate(data.memo_items):
        before = old.get(item.id)
        completed = (before['completed_at'] if before and before['is_completed'] else datetime.now(timezone.utc)) if item.is_completed else None
        if before:
            run(db,'''UPDATE app.memo_items SET text=%s,position=%s,is_completed=%s,completed_at=%s,updated_at=now()
                WHERE owner_id=%s AND memo_card_id=%s AND id=%s''',(item.text,position,item.is_completed,completed,owner,card_id,item.id))
        else:
            run(db,'''INSERT INTO app.memo_items(id,owner_id,memo_card_id,text,position,is_completed,completed_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s)''',(item.id,owner,card_id,item.text,position,item.is_completed,completed))
        run(db,'DELETE FROM app.memo_item_links WHERE owner_id=%s AND item_id=%s',(owner,item.id))
        for target in item.target_ids:
            run(db,'INSERT INTO app.memo_item_links(owner_id,memo_card_id,item_id,target_card_id) VALUES(%s,%s,%s,%s)',(owner,card_id,item.id,target))


def active(row):
    if row['kind'] != 'memo' or row['memo_format'] != 'checklist':
        fail(422,'invalid_memo','请选择备忘清单')
    if row['lifecycle'] != 'active':
        fail(409,'memo_unavailable','请先恢复备忘再操作')


def complete(db, owner, card_id, item_id, body):
    from app.services.cards import detail, event
    with db.transaction():
        parent = owned(db,'cards',owner,card_id,lock=True)
        active(parent); revision(parent,body.expected_revision)
        row = one(db,'SELECT * FROM app.memo_items WHERE owner_id=%s AND memo_card_id=%s AND id=%s',(owner,card_id,item_id))
        if not row: fail(404,'not_found','条目不存在或不可用')
        if row['is_completed'] != body.is_completed:
            run(db,'UPDATE app.memo_items SET is_completed=%s,completed_at=%s,updated_at=now() WHERE owner_id=%s AND id=%s',
                (body.is_completed,datetime.now(timezone.utc) if body.is_completed else None,owner,item_id))
            run(db,'UPDATE app.cards SET revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',(owner,card_id))
            event(db,owner,'memo_item_completed' if body.is_completed else 'memo_item_reopened',parent)
    return detail(db,owner,card_id)


def reorder(db, owner, card_id, body):
    from app.services.cards import detail, event
    with db.transaction():
        parent = owned(db,'cards',owner,card_id,lock=True)
        active(parent); revision(parent,body.expected_revision)
        current = [row['id'] for row in many(db,'SELECT id FROM app.memo_items WHERE owner_id=%s AND memo_card_id=%s ORDER BY position',(owner,card_id))]
        if len(body.item_ids)!=len(set(body.item_ids)) or set(body.item_ids)!=set(current):
            fail(422,'invalid_order','重排必须包含全部条目且不能重复')
        if current != body.item_ids:
            for position,item_id in enumerate(body.item_ids):
                run(db,'UPDATE app.memo_items SET position=%s WHERE owner_id=%s AND memo_card_id=%s AND id=%s',(position,owner,card_id,item_id))
            run(db,'UPDATE app.cards SET revision=revision+1,updated_at=now() WHERE owner_id=%s AND id=%s',(owner,card_id))
            event(db,owner,'memo_updated',parent)
    return detail(db,owner,card_id)


def listing(db, owner, *, is_completed=False, q=None, limit=24, offset=0):
    where=' WHERE i.owner_id=%s AND c.lifecycle=\'active\' AND i.is_completed=%s'
    args=[owner,is_completed]
    if q:
        pattern='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        where+=" AND (c.title ILIKE %s ESCAPE '\\' OR i.text ILIKE %s ESCAPE '\\')"
        args.extend([pattern,pattern])
    source=' FROM app.memo_items i JOIN app.cards c ON c.owner_id=i.owner_id AND c.id=i.memo_card_id'
    total=one(db,'SELECT count(*) AS n'+source+where,args)['n']
    rows=many(db,'''SELECT i.id,i.text,i.is_completed,i.completed_at,c.id AS memo_card_id,c.title AS memo_title,c.revision'''+source+where+
        ' ORDER BY c.updated_at DESC,c.id,i.position,i.id LIMIT %s OFFSET %s',(*args,limit,offset))
    for row in rows:
        row['targets']=many(db,'''SELECT c.id,c.title,c.kind,c.lifecycle FROM app.memo_item_links l JOIN app.cards c
            ON c.owner_id=l.owner_id AND c.id=l.target_card_id WHERE l.owner_id=%s AND l.item_id=%s ORDER BY c.title,c.id''',(owner,row['id']))
    return {'items':rows,'total':total,'limit':limit,'offset':offset}
