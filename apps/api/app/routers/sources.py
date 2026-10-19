from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.repositories.workspace import fail
from app.routers.workspace import Owner
from app.services.source_capture import limited_resolve
from app.services.source_http import FetchError

router = APIRouter(prefix='/api/sources')


class SourceRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    mode: Literal['auto', 'webpage'] = 'auto'


@router.post('/resolve')
def resolve_source(body: SourceRequest, owner: Owner):
    try:
        return limited_resolve(owner, body.url, body.mode)
    except FetchError as exc:
        code = str(exc)
        if code in ('rate_limited', 'busy'):
            fail(429, 'source_busy', '来源获取较频繁，请稍后重试；也可手动填写。')
        fail(422, 'source_url', '请使用不含账号密码的公开HTTP(S)链接和标准端口。')
