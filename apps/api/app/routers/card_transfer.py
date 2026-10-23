"""Authenticated portable card package endpoints."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from app.routers.workspace import Db, Owner
from app.services.card_package import Package
from app.services.card_transfer import import_package, export_package
from app.media_storage import MediaConfig, MediaError
from app.repositories.workspace import fail

router = APIRouter(prefix='/api/card-transfer')

@router.post('/validate')
def validate(owner: Owner, file: Annotated[UploadFile, File()]):
    try:
        package = Package(file.file)
        try:
            return JSONResponse(package.summary(), headers={'Cache-Control':'private, no-store'})
        finally:
            package.close()
    except (MediaError, OSError):
        fail(422,'media_unavailable','图片无法校验，请检查文件与媒体配置')

@router.post('/import')
def import_cards(db: Db, owner: Owner, file: Annotated[UploadFile, File()],
                 batch_id: Annotated[UUID, Form()], expected_digest: Annotated[str, Form(pattern=r'^[0-9a-f]{64}$')]):
    try:
        package = Package(file.file)
        try:
            return JSONResponse(import_package(db,owner,package,batch_id,expected_digest),headers={'Cache-Control':'private, no-store'})
        finally:
            package.close()
    except (MediaError, OSError):
        fail(503,'media_unavailable','图片存储不可用，未导入卡片，可用同一批次重试')

@router.get('/export')
def export_cards(db: Db, owner: Owner, format: Literal['json','zip']='zip'):
    try:
        path = export_package(db,owner,format,MediaConfig.load())
    except (MediaError, OSError):
        fail(503,'media_unavailable','原图缺失或存储不可用，无法完整导出')
    return FileResponse(path, media_type='application/zip' if format=='zip' else 'application/json',
                        filename='selflore-cards.'+format, headers={'Cache-Control':'private, no-store'},
                        background=BackgroundTask(path.unlink,missing_ok=True))


# Public, versioned documentation is shipped with the API, independent of web dist.
from pathlib import Path
from fastapi.responses import Response
DOCS = Path(__file__).resolve().parents[1] / 'transfer_docs'

@router.get('/schema')
def schema():
    return FileResponse(DOCS / 'v1.schema.json', media_type='application/schema+json', filename='v1.schema.json')

@router.get('/example')
def example():
    return FileResponse(DOCS / 'example.json', media_type='application/json', filename='selflore-example.json')

@router.get('/guide')
def guide():
    return Response((DOCS / 'guide.md').read_text(encoding='utf-8-sig'), media_type='text/plain; charset=utf-8')
