from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.repositories.workspace import one,many,run,revision,fail


def profile(db,owner):
    query='SELECT p.*,u.username FROM app.user_profiles p JOIN app.users u ON u.id=p.user_id WHERE p.user_id=%s'
    row=one(db,query,(owner,))
    if row is None:
        # An account created by a rolled-back identity-only application still gets its defaults.
        run(db,'INSERT INTO app.user_profiles(user_id,display_name) SELECT id,username FROM app.users WHERE id=%s ON CONFLICT DO NOTHING',(owner,))
        row=one(db,query,(owner,))
    if not row: fail(503,'schema_missing','资料尚未初始化，请完成数据库迁移')
    return row


def edit(db,owner,body):
    with db.transaction():
        row=one(db,'SELECT * FROM app.user_profiles WHERE user_id=%s FOR UPDATE',(owner,))
        revision(row,body.expected_revision)
        values=body.model_dump(exclude_unset=True,exclude={'expected_revision'})
        if any(value is None for value in values.values()): fail(422,'invalid_profile','资料字段不能为空值')
        if values:
            run(db,'UPDATE app.user_profiles SET '+','.join(k+'=%s' for k in values)+',revision=revision+1,updated_at=now() WHERE user_id=%s',(*values.values(),owner))
    return profile(db,owner)


def day_bounds(db,owner,now=None):
    settings=profile(db,owner); now=now or datetime.now(timezone.utc)
    today=now.astimezone(ZoneInfo(settings['timezone'])).date()
    start=datetime.combine(today,datetime.min.time(),ZoneInfo(settings['timezone']))
    return settings,today,start.astimezone(timezone.utc),(start+timedelta(days=1)).astimezone(timezone.utc)


def learning_days(db,owner):
    tz=profile(db,owner)['timezone']
    return many(db,"""SELECT (occurred_at AT TIME ZONE %s)::date AS day,count(*) AS count
      FROM app.activity_events WHERE owner_id=%s AND event_kind IN ('card_created','card_updated','reviewed')
      GROUP BY day ORDER BY day""",(tz,owner))


def summary(db,owner,now=None):
    _,today,_,_=day_bounds(db,owner,now)
    dates={row['day'] for row in learning_days(db,owner)}
    day=today if today in dates else today-timedelta(days=1); streak=0
    while day in dates:
        streak+=1; day-=timedelta(days=1)
    totals=one(db,"SELECT count(*) FILTER(WHERE kind='knowledge') AS knowledge,count(*) FILTER(WHERE kind='opinion') AS opinions FROM app.cards WHERE owner_id=%s AND lifecycle<>'trashed'",(owner,))
    totals['collections']=one(db,"SELECT count(*) AS n FROM app.collections WHERE owner_id=%s AND lifecycle='active'",(owner,))['n']
    totals['streak']=streak
    return totals


def heatmap(db,owner,now=None):
    settings,today,_,_=day_bounds(db,owner,now)
    start=today-timedelta(days=today.weekday()+77)
    counts={r['day']:r['count'] for r in learning_days(db,owner)}
    return {'timezone':settings['timezone'],'start':start,'end':start+timedelta(days=83),
            'days':[{'date':start+timedelta(days=i),'count':counts.get(start+timedelta(days=i),0),'is_future':start+timedelta(days=i)>today} for i in range(84)]}


def activity(db,owner,kind=None,limit=24,offset=0):
    where=' WHERE a.owner_id=%s'; values=[owner]
    if kind in ('knowledge','opinion'):
        where+=' AND c.kind=%s'; values.append(kind)
    elif kind=='collection':
        where+=' AND a.collection_id IS NOT NULL'
    query=' FROM app.activity_events a LEFT JOIN app.cards c ON c.owner_id=a.owner_id AND c.id=a.card_id LEFT JOIN app.collections x ON x.owner_id=a.owner_id AND x.id=a.collection_id'
    total=one(db,'SELECT count(*) AS n'+query+where,values)['n']
    rows=many(db,"SELECT a.id,a.card_id,a.collection_id,a.event_kind,a.entity_title,a.occurred_at,c.kind,COALESCE(c.lifecycle,x.lifecycle) AS lifecycle"+query+where+' ORDER BY a.occurred_at DESC,a.id DESC LIMIT %s OFFSET %s',(*values,limit,offset))
    return {'items':rows,'total':total,'limit':limit,'offset':offset}
