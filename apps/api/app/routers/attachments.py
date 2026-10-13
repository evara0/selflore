from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID
import re

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.media_storage import MediaConfig, MediaError, safe_path
from app.routers.workspace import Db, Owner
from app.repositories.workspace import fail
from app.services import attachments

router = APIRouter(prefix='/api/attachments')


@router.get('/config')
def configuration(owner: Owner):
    config = MediaConfig.load()
    try:
        config.check(); available = True
    except (MediaError, OSError):
        available = False
    return {**config.limits(), 'is_available': available}


@router.post('', status_code=201)
def upload(db: Db, owner: Owner, file: Annotated[UploadFile, File()],
           client_request_id: Annotated[UUID, Form()], file_sha256: Annotated[str, Form(max_length=64)]):
    if not re.fullmatch('[0-9a-f]{64}', file_sha256):
        fail(422,'image_digest','图片校验值不合法')
    try:
        return attachments.upload(db, owner, client_request_id, file_sha256, file.file, MediaConfig.load())
    finally:
        file.file.close()


@router.get('/{entity}')
def metadata(entity: UUID, db: Db, owner: Owner):
    return attachments.public(attachments.metadata(db, owner, entity))


@router.get('/{entity}/content')
def content(entity: UUID, db: Db, owner: Owner, variant: Literal['original','thumbnail']='thumbnail'):
    row = attachments.metadata(db, owner, entity)
    if row['status'] != 'ready':
        fail(404,'not_found','图片尚未完成或不可用')
    try:
        config = MediaConfig.load()
        path = safe_path(config.check(), row[variant+'_key'])
        if not path.is_file():
            fail(404,'image_missing','图片文件缺失，请运行存储排查')
        return FileResponse(path, media_type=row['mime_type'] if variant=='original' else 'image/webp',
                            headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    except (MediaError, OSError):
        fail(503,'storage_unavailable','图片存储不可用，请运行存储排查')
