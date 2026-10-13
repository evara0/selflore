"""Upload attempts publish immutable files before a ready database record."""
from __future__ import annotations

import hashlib
import os
from uuid import uuid4
from fastapi import HTTPException

from app.media_storage import MediaConfig, MediaError, file_hash, safe_path, image_thumbnail
from app.repositories.workspace import one, run, fail


def public(row):
    return {k: row[k] for k in ('id', 'status', 'mime_type', 'width', 'height', 'original_bytes', 'thumbnail_bytes', 'created_at')}


def metadata(db, owner, entity):
    row = one(db, 'SELECT * FROM app.attachments WHERE owner_id=%s AND id=%s', (owner, entity))
    if not row:
        fail(404, 'not_found', '附件不存在或不可用')
    return row


def upload(db, owner, request_id, expected_hash, stream, config: MediaConfig):
    try:
        root = config.check()
    except (MediaError, OSError):
        fail(503, 'storage_unavailable', '图片存储未配置或不可用，请运行配置／排查入口')
    lock = int.from_bytes(hashlib.sha256(f'{owner}:{request_id}'.encode()).digest()[:8], 'big', signed=True)
    if not one(db, 'SELECT pg_try_advisory_lock(%s) AS locked', (lock,))['locked']:
        fail(409, 'upload_pending', '同一图片正在上传，请稍后重试')
    db.commit()
    row = None
    attempt_files = []
    try:
        row = one(db, 'SELECT * FROM app.attachments WHERE owner_id=%s AND client_request_id=%s', (owner, request_id))
        if row and row['request_sha256'] != expected_hash:
            fail(409, 'request_conflict', '上传标识已用于不同文件')
        # Verify actual bytes even for retries; never trust the declared fingerprint.
        attempt = uuid4()
        key = f'{owner}/{row["id"] if row else uuid4()}/{attempt}'
        original = safe_path(root, key + '/original.bin')
        original.parent.mkdir(parents=True, exist_ok=False)
        thumbnail = safe_path(root, key + '/thumbnail.webp')
        attempt_files = [original, thumbnail]
        if not row:
            entity = original.parent.parent.name
            row = one(db, '''INSERT INTO app.attachments(id,owner_id,status,client_request_id,request_sha256)
                       VALUES(%s,%s,'uploading',%s,%s) RETURNING *''', (entity, owner, request_id, expected_hash))
        db.commit()
        digest = hashlib.sha256(); size = 0
        with original.open('xb') as output:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > config.max_bytes:
                    fail(413, 'image_too_large', '图片文件超过上传大小限制')
                output.write(chunk); digest.update(chunk)
            output.flush(); os.fsync(output.fileno())
        if not size or digest.hexdigest() != expected_hash:
            fail(422, 'image_digest', '图片内容为空或校验不符')
        if row['status'] == 'ready':
            return public(row)
        image = image_thumbnail(original, thumbnail, config)
        # Publish the directory: after rename the attempt is immutable and retained even on DB failure.
        published = safe_path(root, key + '-ready')
        original.parent.rename(published)
        attempt_files = []
        original, thumbnail = published / 'original.bin', published / 'thumbnail.webp'
        row = one(db, '''UPDATE app.attachments SET status='ready',original_key=%s,thumbnail_key=%s,
                     original_bytes=%s,thumbnail_bytes=%s,original_sha256=%s,thumbnail_sha256=%s,
                     mime_type=%s,width=%s,height=%s,updated_at=now() WHERE owner_id=%s AND id=%s RETURNING *''',
                  (original.relative_to(root).as_posix(), thumbnail.relative_to(root).as_posix(), size,
                   thumbnail.stat().st_size, expected_hash, file_hash(thumbnail), image['mime_type'], image['width'],
                   image['height'], owner, row['id']))
        db.commit()
        return public(row)
    except (MediaError, OSError) as error:
        db.rollback()
        if row and row['status'] != 'ready':
            run(db, "UPDATE app.attachments SET status='failed',updated_at=now() WHERE owner_id=%s AND id=%s AND status<>'ready'", (owner, row['id']))
            db.commit()
        fail(422 if isinstance(error, MediaError) else 503, 'image_failed',
             str(error) if isinstance(error, MediaError) else '图片写入失败，请检查磁盘及权限')
    except Exception:
        db.rollback()
        if row and row['status'] != 'ready':
            run(db, "UPDATE app.attachments SET status='failed',updated_at=now() WHERE owner_id=%s AND id=%s AND status<>'ready'", (owner, row['id']))
            db.commit()
        raise
    finally:
        for path in attempt_files:
            if path.is_file():
                path.unlink()
        one(db, 'SELECT pg_advisory_unlock(%s)', (lock,)); db.commit()
