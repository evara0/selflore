from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID, uuid4
import unicodedata
import psycopg
from fastapi import APIRouter, Depends, Query, Request

from app.auth import get_db,get_settings,current_user,Settings,_origin,_csrf
from app.repositories.workspace import one,many,run,fail
from app.schemas.workspace import CardCreate,CardPatch,Lifecycle,Revision,TaxonomyCreate,TaxonomyPatch,CollectionCreate,CollectionPatch,Members,Order,RatingInput,ProfilePatch
from app.services import cards,collections,reviews,profiles

router=APIRouter(prefix='/api')
Db=Annotated[psycopg.Connection,Depends(get_db)]


def actor(request:Request,user:Annotated[tuple,Depends(current_user)],settings:Annotated[Settings,Depends(get_settings)]):
    if request.method in {'POST','PATCH','PUT','DELETE'}:
        _origin(request,settings); _csrf(request,user[4])
    return user[0]


Owner=Annotated[UUID,Depends(actor)]
Limit=Annotated[int,Query(ge=1,le=100)]
Offset=Annotated[int,Query(ge=0)]


@router.get('/cards')
def card_list(db:Db,owner:Owner,kind:Literal['knowledge','opinion']|None=None,q:Annotated[str|None,Query(max_length=200)]=None,
    topic_id:UUID|None=None,tag_id:UUID|None=None,lifecycle:Literal['active','archived','trashed']='active',
    processing_state:Literal['inbox','organized']|None=None,is_bookmarked:bool|None=None,
    sort:Literal['updated_desc','created_desc','code_asc','connections_desc']='updated_desc',limit:Limit=24,offset:Offset=0):
    return cards.list_cards(db,owner,kind=kind,q=q,topic_id=topic_id,tag_id=tag_id,lifecycle=lifecycle,
        processing_state=processing_state,is_bookmarked=is_bookmarked,sort=sort,limit=limit,offset=offset)


@router.post('/cards',status_code=201)
def card_create(body:CardCreate,db:Db,owner:Owner):
    return cards.create_card(db,owner,body)


@router.get('/cards/summary')
def card_summary(db:Db,owner:Owner):
    return one(db,"""SELECT count(*) FILTER(WHERE kind='knowledge') AS knowledge,count(*) FILTER(WHERE kind='opinion') AS opinions,
      count(*) FILTER(WHERE processing_state='inbox') AS inbox,count(*) FILTER(WHERE is_bookmarked) AS bookmarked
      FROM app.cards WHERE owner_id=%s AND lifecycle='active'""",(owner,))


@router.get('/cards/{entity}')
def card_detail(entity:UUID,db:Db,owner:Owner): return cards.detail(db,owner,entity)


@router.patch('/cards/{entity}')
def card_edit(entity:UUID,body:CardPatch,db:Db,owner:Owner): return cards.edit_card(db,owner,entity,body)


@router.post('/cards/{entity}/lifecycle')
def card_lifecycle(entity:UUID,body:Lifecycle,db:Db,owner:Owner): return cards.change_lifecycle(db,'cards',owner,entity,body.action,body.expected_revision)


@router.get('/cards/{entity}/links')
def links(entity:UUID,db:Db,owner:Owner): return cards.link_list(db,owner,entity)


@router.post('/cards/{entity}/links/{target}')
def add_link(entity:UUID,target:UUID,body:Revision,db:Db,owner:Owner): return cards.manual_link(db,owner,entity,target,body.expected_revision)


@router.delete('/cards/{entity}/links/{target}')
def remove_link(entity:UUID,target:UUID,body:Revision,db:Db,owner:Owner): return cards.manual_link(db,owner,entity,target,body.expected_revision,True)


def taxonomy_list(db,owner,table,kind=None):
    relation,key=('card_topics','topic_id') if table=='topics' else ('card_tags','tag_id')
    query=f"""SELECT t.*,(SELECT count(*) FROM app.{relation} r JOIN app.cards c ON c.owner_id=r.owner_id AND c.id=r.card_id
      WHERE r.owner_id=t.owner_id AND r.{key}=t.id AND c.lifecycle='active') AS card_count FROM app.{table} t WHERE t.owner_id=%s"""
    rows=many(db,query+(' AND t.kind=%s' if kind and table=='topics' else '')+' ORDER BY t.name',(owner,kind) if kind and table=='topics' else (owner,))
    return {'items':[{k:v for k,v in row.items() if k!='owner_id'} for row in rows]}


def taxonomy_write(db,owner,table,body,entity=None):
    name=unicodedata.normalize('NFKC',body.name).strip()
    if not name or len(name)>(80 if table=='topics' else 32): fail(422,'invalid_name','名称长度不合法')
    try:
        with db.transaction():
            if entity:
                row=one(db,f'UPDATE app.{table} SET name=%s WHERE owner_id=%s AND id=%s RETURNING id,name',(name,owner,entity))
                if not row: fail(404,'not_found','对象不存在或不可用')
            else:
                entity=uuid4()
                if table=='topics':
                    if not body.kind: fail(422,'missing_kind','请选择分类类型')
                    row=one(db,'INSERT INTO app.topics(id,owner_id,kind,name) VALUES(%s,%s,%s,%s) RETURNING id,name,kind',(entity,owner,body.kind,name))
                else:
                    row=one(db,'INSERT INTO app.tags(id,owner_id,name) VALUES(%s,%s,%s) RETURNING id,name',(entity,owner,name))
    except psycopg.errors.UniqueViolation: fail(409,'duplicate','名称已存在')
    return row


def taxonomy_delete(db,owner,table,entity):
    try:
        with db.transaction():
            row=one(db,f'DELETE FROM app.{table} WHERE owner_id=%s AND id=%s RETURNING id',(owner,entity))
            if not row: fail(404,'not_found','对象不存在或不可用')
    except psycopg.errors.ForeignKeyViolation: fail(409,'in_use','仍被卡片使用，请先移除关联')


@router.get('/topics')
def topics(db:Db,owner:Owner,kind:Literal['knowledge','opinion']|None=None): return taxonomy_list(db,owner,'topics',kind)


@router.post('/topics',status_code=201)
def create_topic(body:TaxonomyCreate,db:Db,owner:Owner): return taxonomy_write(db,owner,'topics',body)


@router.patch('/topics/{entity}')
def edit_topic(entity:UUID,body:TaxonomyPatch,db:Db,owner:Owner): return taxonomy_write(db,owner,'topics',body,entity)


@router.delete('/topics/{entity}',status_code=204)
def delete_topic(entity:UUID,db:Db,owner:Owner): taxonomy_delete(db,owner,'topics',entity)


@router.get('/tags')
def tags(db:Db,owner:Owner): return taxonomy_list(db,owner,'tags')


@router.post('/tags',status_code=201)
def create_tag(body:TaxonomyCreate,db:Db,owner:Owner): return taxonomy_write(db,owner,'tags',body)


@router.patch('/tags/{entity}')
def edit_tag(entity:UUID,body:TaxonomyPatch,db:Db,owner:Owner): return taxonomy_write(db,owner,'tags',body,entity)


@router.delete('/tags/{entity}',status_code=204)
def delete_tag(entity:UUID,db:Db,owner:Owner): taxonomy_delete(db,owner,'tags',entity)


@router.get('/collections')
def collection_list(db:Db,owner:Owner,q:Annotated[str|None,Query(max_length=200)]=None,is_favorite:bool|None=None,lifecycle:Literal['active','trashed']='active',limit:Limit=24,offset:Offset=0):
    return collections.listing(db,owner,q,is_favorite,lifecycle,limit,offset)


@router.post('/collections',status_code=201)
def create_collection(body:CollectionCreate,db:Db,owner:Owner): return collections.create(db,owner,body)


@router.get('/collections/{entity}')
def collection_detail(entity:UUID,db:Db,owner:Owner): return collections.detail(db,owner,entity)


@router.patch('/collections/{entity}')
def edit_collection(entity:UUID,body:CollectionPatch,db:Db,owner:Owner): return collections.edit(db,owner,entity,body)


@router.post('/collections/{entity}/lifecycle')
def collection_lifecycle(entity:UUID,body:Lifecycle,db:Db,owner:Owner): return collections.lifecycle(db,owner,entity,body)


@router.get('/collections/{entity}/items')
def collection_items(entity:UUID,db:Db,owner:Owner): return collections.items(db,owner,entity)


@router.post('/collections/{entity}/items')
def add_items(entity:UUID,body:Members,db:Db,owner:Owner): return collections.update_items(db,owner,entity,body.expected_revision,add=body.card_ids)


@router.delete('/collections/{entity}/items/{item}')
def remove_item(entity:UUID,item:UUID,body:Revision,db:Db,owner:Owner): return collections.update_items(db,owner,entity,body.expected_revision,remove=item)


@router.put('/collections/{entity}/order')
def reorder(entity:UUID,body:Order,db:Db,owner:Owner): return collections.update_items(db,owner,entity,body.expected_revision,order=body.item_ids)


@router.get('/reviews/queue')
def review_queue(db:Db,owner:Owner,topic_id:UUID|None=None,limit:Limit=100): return reviews.queue(db,owner,topic_id,limit)


@router.get('/reviews/summary')
def review_summary(db:Db,owner:Owner): return reviews.summary(db,owner)


@router.get('/reviews/units/{entity}/preview')
def review_preview(entity:UUID,db:Db,owner:Owner): return reviews.preview(db,owner,entity)


@router.post('/reviews/units/{entity}/ratings')
def review_rating(entity:UUID,body:RatingInput,db:Db,owner:Owner): return reviews.rate(db,owner,entity,body)


@router.get('/me/profile')
def me_profile(db:Db,owner:Owner): return profiles.profile(db,owner)


@router.patch('/me/profile')
def profile_edit(body:ProfilePatch,db:Db,owner:Owner): return profiles.edit(db,owner,body)


@router.get('/me/summary')
def me_summary(db:Db,owner:Owner): return profiles.summary(db,owner)


@router.get('/me/activity')
def me_activity(db:Db,owner:Owner,kind:Literal['knowledge','opinion','collection']|None=None,limit:Limit=24,offset:Offset=0): return profiles.activity(db,owner,kind,limit,offset)


@router.get('/me/heatmap')
def me_heatmap(db:Db,owner:Owner): return profiles.heatmap(db,owner)


@router.get('/me/pinned-collections')
def pinned(db:Db,owner:Owner):
    rows=many(db,collections.SELECT+" WHERE c.owner_id=%s AND c.is_pinned AND c.lifecycle='active' ORDER BY c.updated_at DESC,c.id DESC LIMIT 6",(owner,))
    return {'items':[collections.public(row) for row in rows]}
