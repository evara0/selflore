"""Transactional import and consistent full-content export."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4
import zipfile
from psycopg.types.json import Jsonb
from app.repositories.workspace import one, many, run, fail
from app.schemas.workspace import CardContent
from app.schemas.card_transfer import MAX_CARDS, MAX_JSON, MAX_ARCHIVE, EXCLUDED, TransferDocument
from app.services import cards, memos
from app.services.card_package import rewrite, TEXT_FIELDS, issue
from app.media_storage import safe_path, file_hash


def recover_attempt(db, owner, batch_id, config):
    """Only inspect exact attempt paths recorded by this owner/batch; never delete ready files."""
    root = config.check()
    ops = config.check(ops=True)
    journal_key = hashlib.sha256(f'{owner}:{batch_id}'.encode()).hexdigest()[:32]
    journal = safe_path(ops, f'transfer-{journal_key}.json')
    if journal.exists():
        previous = json.loads(journal.read_text(encoding='utf-8'))
        for entry in previous:
            entity = entry['id']
            # Reconstruct the directory, never trust a path from the journal.
            directory = safe_path(root, f'{UUID(str(owner)).hex}/{UUID(str(entity)).hex}')
            ready = one(db, 'SELECT id FROM app.attachments WHERE owner_id=%s AND id=%s', (owner, entity))
            if not ready and directory.exists():
                for name in ('original.bin', 'thumbnail.webp'):
                    path = safe_path(root, f'{UUID(str(owner)).hex}/{UUID(str(entity)).hex}/{name}')
                    path.unlink(missing_ok=True)
                directory.rmdir()
    return root, journal


def import_package(db, owner, package, batch_id, expected_digest):
    if package.digest != expected_digest:
        fail(409, 'preview_changed', '文件已改变，请重新预检')
    document = package.document
    # Authentication reads precede this service; start an actual outer transaction.
    db.commit()
    with db.transaction():
        lock = int.from_bytes(hashlib.sha256(f'transfer:{owner}:{batch_id}'.encode()).digest()[:8], 'big', signed=True)
        one(db, 'SELECT pg_advisory_xact_lock(%s)', (lock,))
        old = one(db, 'SELECT digest,result FROM app.card_import_batches WHERE owner_id=%s AND batch_id=%s', (owner,batch_id))
        if old:
            if old['digest'] != package.digest:
                fail(409, 'batch_conflict', '批次标识已用于不同内容')
            return old['result']
        identities = {c.key: uuid4() for c in document.cards}
        assets = {a.key: uuid4() for a in document.assets}
        item_ids = {c.key: {i.key: uuid4() for i in c.memo_items} for c in document.cards}
        if assets:
            root, journal = recover_attempt(db, owner, batch_id, package.config)
            records = [{'id': str(assets[a.key])} for a in document.assets]
            temporary = journal.with_suffix('.pending')
            temporary.write_text(json.dumps(records), encoding='utf-8')
            with temporary.open('r+b') as stream:
                os.fsync(stream.fileno())
            temporary.replace(journal)
            for asset in document.assets:
                original, thumb, meta = package.images[asset.key]
                entity = assets[asset.key]
                prefix = f'{UUID(str(owner)).hex}/{UUID(str(entity)).hex}'
                output = safe_path(root, prefix + '/original.bin')
                output.parent.mkdir(parents=True, exist_ok=False)
                preview = safe_path(root, prefix + '/thumbnail.webp')
                shutil.copyfile(original, output)
                shutil.copyfile(thumb, preview)
                for path in (output, preview):
                    with path.open('r+b') as stream:
                        os.fsync(stream.fileno())
                run(db, '''INSERT INTO app.attachments(id,owner_id,status,client_request_id,request_sha256,
                    original_key,thumbnail_key,original_bytes,thumbnail_bytes,original_sha256,thumbnail_sha256,mime_type,width,height)
                    VALUES(%s,%s,'ready',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (entity,owner,uuid4(),asset.sha256,prefix+'/original.bin',prefix+'/thumbnail.webp',asset.bytes,
                     preview.stat().st_size,asset.sha256,file_hash(preview),meta['mime_type'],meta['width'],meta['height']))
        payloads = {}
        # All nodes exist before any edge is resolved.
        for card in document.cards:
            payload = card.model_dump(exclude={'key','tags','lifecycle','link_keys','memo_items','attachments'})
            for field in TEXT_FIELDS:
                payload[field] = rewrite(payload[field], identities, importing=True)
            payload['memo_items'] = [dict(id=item_ids[card.key][i.key], text=i.text, extra_values=i.extra_values,
                                         is_completed=i.is_completed, target_ids=[]) for i in card.memo_items]
            payload['attachments'] = [dict(id=assets[a.asset_key], caption=a.caption,alt_text=a.alt_text,creator_name=a.creator_name) for a in card.attachments]
            payload['taxonomy_mode'] = 'unified'
            tag_ids = []
            for name in card.tags:
                row = one(db, '''INSERT INTO app.tags(id,owner_id,name) VALUES(%s,%s,%s)
                    ON CONFLICT(owner_id,normalized_name) DO UPDATE SET name=app.tags.name RETURNING id''', (uuid4(),owner,name))
                tag_ids.append(row['id'])
            payload['tag_ids'] = tag_ids
            data = CardContent.model_validate(payload)
            payloads[card.key] = data
            values = data.model_dump()
            entity = identities[card.key]
            code = datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + entity.hex.upper()
            columns = ('id','owner_id','code',*cards.FIELDS,'search_text','client_request_id','creation_request_digest','lifecycle','trashed_at')
            params = (entity,owner,code,*(values[k] for k in cards.FIELDS),cards.search_text(values,code),uuid4(),cards.digest(values),card.lifecycle,datetime.now(timezone.utc) if card.lifecycle=='trashed' else None)
            run(db, 'INSERT INTO app.cards('+','.join(columns)+') VALUES('+','.join(['%s']*len(params))+')', params)
        for card in document.cards:
            entity = identities[card.key]
            data = payloads[card.key]
            memos.sync(db,owner,entity,data)
            cards.relations(db,owner,entity,data)
            cards.sync_units(db,owner,entity,data)
            for i in card.memo_items:
                item_id = item_ids[card.key][i.key]
                if i.completed_at:
                    run(db,'UPDATE app.memo_items SET completed_at=%s WHERE owner_id=%s AND id=%s',(i.completed_at,owner,item_id))
                for target in i.target_keys:
                    run(db,'INSERT INTO app.memo_item_links(owner_id,memo_card_id,item_id,target_card_id) VALUES(%s,%s,%s,%s)',(owner,entity,item_id,identities[target]))
            for target in card.link_keys:
                run(db,"INSERT INTO app.card_links(owner_id,source_card_id,target_card_id,origin) VALUES(%s,%s,%s,'manual')",(owner,entity,identities[target]))
            cards.event(db,owner,'memo_created' if card.kind=='memo' else 'card_created',dict(id=entity,title=card.title))
        result = dict(card_count=len(identities), asset_count=len(assets),
                      mapping={key:str(value) for key,value in identities.items()},
                      asset_mapping={key:str(value) for key,value in assets.items()},
                      item_mapping={key:{k:str(v) for k,v in values.items()} for key,values in item_ids.items()})
        run(db,'INSERT INTO app.card_import_batches(owner_id,batch_id,digest,result) VALUES(%s,%s,%s,%s)',(owner,batch_id,package.digest,Jsonb(result)))
    return result


def export_package(db, owner, format, config):
    db.commit()
    with db.transaction():
        run(db,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        count = one(db,'SELECT count(*) AS n FROM app.cards WHERE owner_id=%s',(owner,))['n']
        if count > MAX_CARDS:
            fail(413,'transfer_limit','卡片超过2000张，无法生成完整备份；未导出部分内容')
        rows = many(db,'SELECT id FROM app.cards WHERE owner_id=%s ORDER BY id',(owner,))
        mapping = {str(row['id']):'card-'+row['id'].hex for row in rows}
        asset_rows = many(db,'''SELECT DISTINCT a.* FROM app.attachments a JOIN app.card_attachments ca
            ON ca.owner_id=a.owner_id AND ca.attachment_id=a.id WHERE a.owner_id=%s ORDER BY a.id''',(owner,))
        if asset_rows and format == 'json':
            fail(409,'zip_required','内容包含图片，请选择ZIP完整导出')
        assets = []
        asset_map = {}
        for row in asset_rows:
            if row['status'] != 'ready':
                issue('assets','附件尚未完成，无法完整导出')
            key = 'asset-' + row['id'].hex
            asset_map[row['id']] = key
            extension = {'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[row['mime_type']]
            assets.append(dict(key=key,path=f'media/{key}.{extension}',sha256=row['original_sha256'],bytes=row['original_bytes'],mime_type=row['mime_type']))
        entries = []
        for row in rows:
            detail = cards.detail(db,owner,row['id'])
            entry = {field:detail[field] for field in cards.FIELDS}
            entry.update(key=mapping[str(row['id'])],lifecycle=detail['lifecycle'],tags=[t['name'] for t in detail['tags']])
            for field in TEXT_FIELDS:
                try:
                    entry[field] = rewrite(entry[field],mapping,importing=False)
                except ValueError as error:
                    issue('cards.'+entry['key']+'.'+field,str(error))
            entry['memo_items'] = [dict(key='item-'+i['id'].hex,text=i['text'],extra_values=i['extra_values'],
                is_completed=i['is_completed'],completed_at=i['completed_at'],target_keys=[mapping[str(t)] for t in i['target_ids']]) for i in detail['memo_items']]
            entry['attachments'] = [dict(asset_key=asset_map[a['id']],caption=a['caption'],alt_text=a['alt_text'],creator_name=a['creator_name']) for a in detail['attachments']]
            entry['link_keys'] = [mapping[str(r['target_card_id'])] for r in many(db,"SELECT target_card_id FROM app.card_links WHERE owner_id=%s AND source_card_id=%s AND origin='manual' ORDER BY target_card_id",(owner,row['id']))]
            entries.append(entry)
        document = TransferDocument.model_validate(dict(format='selflore.cards',version=1,cards=entries,assets=assets,
            export_info=dict(generated_at=datetime.now(timezone.utc),card_count=count,excluded=EXCLUDED)))
        raw = document.model_dump_json(indent=2).encode()
        if len(raw) > MAX_JSON or len(raw) + sum(a['bytes'] for a in assets) > MAX_ARCHIVE:
            fail(413,'transfer_limit','内容超过包限制，未生成部分备份')
        root = config.check() if assets else None
        with NamedTemporaryFile(prefix='selflore-export-',suffix='.'+format,delete=False) as output:
            path = Path(output.name)
        try:
            if format == 'json':
                path.write_bytes(raw)
            else:
                with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as archive:
                    archive.writestr('manifest.json',raw)
                    for row, asset in zip(asset_rows,assets):
                        original = safe_path(root,row['original_key'])
                        if original.stat().st_size != row['original_bytes'] or file_hash(original) != row['original_sha256']:
                            issue('assets.'+asset['key'],'原图缺失或损坏，无法完整导出')
                        archive.write(original,asset['path'])
            if path.stat().st_size > MAX_ARCHIVE:
                fail(413,'transfer_limit','导出文件超过512 MiB')
            return path
        except BaseException:
            path.unlink(missing_ok=True)
            raise
