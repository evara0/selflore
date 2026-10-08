from __future__ import annotations

from datetime import datetime,timezone
import psycopg
from uuid import uuid4
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

from app.repositories.workspace import one,many,run,owned,fail
from app.services import cards,profiles
from app.services.content import cloze_text
from app.services.scheduling import schedule,VERSION


def unit(db,owner,entity):
    row=one(db,'SELECT u.*,s.state,s.due_at,s.version,s.scheduler_payload,s.scheduler_version,s.review_count,s.lapse_count,s.last_reviewed_at FROM app.review_units u JOIN app.review_states s ON s.owner_id=u.owner_id AND s.unit_id=u.id WHERE u.owner_id=%s AND u.id=%s',(owner,entity))
    if not row: fail(404,'not_found','复习单元不存在或不可用')
    card=cards.detail(db,owner,row['card_id'])
    if not row['is_active'] or card['lifecycle']!='active': fail(409,'unavailable','此卡片当前不可复习')
    return row,card


def render(row,card):
    return {'id':row['id'],'card':card,'state':row['state'],'state_version':row['version'],'due_at':row['due_at'],
            'question':card['question_md'] if card['form']=='qa' else cloze_text(card['body_md'],row['cloze_index'],False),
            'answer':card['answer_md'] if card['form']=='qa' else cloze_text(card['body_md'],row['cloze_index'],True),
            'cloze_index':row['cloze_index']}


def queue(db,owner,topic_id=None,limit=100):
    settings,_,start,end=profiles.day_bounds(db,owner)
    started=one(db,"SELECT count(DISTINCT unit_id) AS n FROM app.review_logs WHERE owner_id=%s AND reviewed_at>=%s AND reviewed_at<%s AND state_before->>'state'='new'",(owner,start,end))['n']
    allowance=max(0,settings['daily_new_limit']-started)
    where="u.owner_id=%s AND u.is_active AND c.lifecycle='active'"
    values=[owner]
    if topic_id:
        where+=' AND EXISTS(SELECT 1 FROM app.card_topics t WHERE t.owner_id=c.owner_id AND t.card_id=c.id AND t.topic_id=%s)'; values.append(topic_id)
    base='SELECT u.id FROM app.review_units u JOIN app.review_states s ON s.owner_id=u.owner_id AND s.unit_id=u.id JOIN app.cards c ON c.owner_id=u.owner_id AND c.id=u.card_id WHERE '+where
    due=many(db,base+" AND s.state<>'new' AND s.due_at<=now() ORDER BY s.due_at,u.id LIMIT %s",(*values,limit))
    new=many(db,base+" AND s.state='new' ORDER BY u.created_at,u.id LIMIT %s",(*values,min(allowance,limit-len(due))))
    result=[]
    for entry in due+new:
        row,card=unit(db,owner,entry['id']); result.append(render(row,card))
    next_due=one(db,base.replace('SELECT u.id','SELECT min(s.due_at) AS due_at')+" AND s.state IN ('learning','relearning') AND s.due_at>now()",values)['due_at']
    return {'items':result,'new_allowance':allowance,'next_due_at':next_due}


def preview(db,owner,entity):
    row,_=unit(db,owner,entity); now=datetime.now(timezone.utc)
    return {'state_version':row['version'],'intervals':[{'rating':rating,'due_at':schedule(row['scheduler_payload'],rating,now)[2],
        'seconds':max(0,int((schedule(row['scheduler_payload'],rating,now)[2]-now).total_seconds()))} for rating in range(1,5)]}


def rate(db,owner,entity,data):
    fingerprint=cards.digest({'unit_id':entity,**data.model_dump(mode='json')})
    def prior():
        old=one(db,'SELECT request_digest,response_payload FROM app.review_logs WHERE owner_id=%s AND request_id=%s',(owner,data.request_id))
        if old:
            if old['request_digest']!=fingerprint: fail(409,'request_conflict','请求标识已用于不同评价')
            return old['response_payload']
        return None
    old=prior()
    if old: return old
    try:
        with db.transaction():
            row,card=unit(db,owner,entity)
            owned(db,'cards',owner,row['card_id'],lock=True)
            one(db,'SELECT id FROM app.review_units WHERE owner_id=%s AND id=%s FOR UPDATE',(owner,entity))
            one(db,'SELECT unit_id FROM app.review_states WHERE owner_id=%s AND unit_id=%s FOR UPDATE',(owner,entity))
            old=prior()
            if old: return old
            row,card=unit(db,owner,entity)
            if row['version']!=data.expected_state_version or card['revision']!=data.expected_content_revision:
                fail(409,'review_conflict','卡片或学习状态已更新，请重新加载')
            if row['scheduler_version']!=VERSION: fail(409,'scheduler_version','请先升级学习状态')
            now=datetime.now(timezone.utc)
            payload,state,due=schedule(row['scheduler_payload'],data.rating,now,data.duration_ms)
            before={'state':row['state'],'version':row['version'],'scheduler_payload':row['scheduler_payload']}
            after={'state':state,'version':row['version']+1,'scheduler_payload':payload}
            response=jsonable_encoder({'unit_id':entity,'state':state,'due_at':due,'state_version':row['version']+1,'request_id':data.request_id})
            run(db,'UPDATE app.review_states SET state=%s,due_at=%s,last_reviewed_at=%s,review_count=review_count+1,lapse_count=lapse_count+%s,scheduler_payload=%s,scheduler_version=%s,version=version+1 WHERE owner_id=%s AND unit_id=%s',
                (state,due,now,int(row['state']=='review' and data.rating==1),Jsonb(payload),VERSION,owner,entity))
            run(db,'INSERT INTO app.review_logs(id,owner_id,unit_id,card_id,request_id,request_digest,rating,reviewed_at,duration_ms,content_revision,state_version_before,scheduler_version,state_before,state_after,content_snapshot,response_payload) VALUES('+','.join(['%s']*16)+')',
                (uuid4(),owner,entity,card['id'],data.request_id,fingerprint,data.rating,now,data.duration_ms,card['revision'],row['version'],VERSION,Jsonb(before),Jsonb(after),Jsonb(jsonable_encoder(card)),Jsonb(response)))
            cards.event(db,owner,'reviewed',card,now=now)
            return response
    except psycopg.errors.UniqueViolation:
        old=prior()
        if old: return old
        fail(409,'request_conflict','评价请求冲突')


def summary(db,owner):
    settings,_,start,end=profiles.day_bounds(db,owner)
    row=one(db,"""SELECT count(*) FILTER(WHERE s.state='new') AS new_units,
      count(*) FILTER(WHERE s.state<>'new' AND s.due_at<=now()) AS due_units
      FROM app.review_units u JOIN app.review_states s ON s.owner_id=u.owner_id AND s.unit_id=u.id
      JOIN app.cards c ON c.owner_id=u.owner_id AND c.id=u.card_id
      WHERE u.owner_id=%s AND u.is_active AND c.lifecycle='active'""",(owner,))
    row['today_completed']=one(db,'SELECT count(DISTINCT unit_id) AS n FROM app.review_logs WHERE owner_id=%s AND reviewed_at>=%s AND reviewed_at<%s',(owner,start,end))['n']
    row['mastered_cards']=one(db,"""SELECT count(*) AS n FROM app.cards c WHERE c.owner_id=%s AND c.kind='knowledge' AND c.lifecycle='active'
      AND EXISTS(SELECT 1 FROM app.review_units u WHERE u.owner_id=c.owner_id AND u.card_id=c.id AND u.is_active)
      AND NOT EXISTS(SELECT 1 FROM app.review_units u LEFT JOIN app.review_states s ON s.owner_id=u.owner_id AND s.unit_id=u.id
         WHERE u.owner_id=c.owner_id AND u.card_id=c.id AND u.is_active AND
           (s.unit_id IS NULL OR s.state<>'review' OR s.last_reviewed_at IS NULL OR s.due_at-s.last_reviewed_at<interval '21 days'))""",(owner,))['n']
    row['daily_review_goal']=settings['daily_review_goal']
    return row
