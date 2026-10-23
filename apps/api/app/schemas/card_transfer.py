"""Portable card content contract; destination UUIDs never appear in AI inputs."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4
from pydantic import Field, create_model, model_validator, field_validator
from app.schemas.workspace import Input, CardContent

MAX_CARDS = 2000
MAX_JSON = 32 * 1024 * 1024
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_MEMBERS = 10001
Key = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')]
EXCLUDED = ['账号凭据与个人资料', '合集结构', '复习历史与调度状态', '活动日志', '未关联图片']

class TransferItem(Input):
    key: Key
    text: str = Field(min_length=1, max_length=2000)
    extra_values: list[str] = Field(default_factory=lambda: ['', ''], min_length=2, max_length=2)
    is_completed: bool = Field(default=False, strict=True)
    completed_at: datetime | None = None
    target_keys: list[Key] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def completion(self):
        if self.completed_at and (not self.is_completed or self.completed_at.tzinfo is None):
            raise ValueError('完成时间需要时区且条目必须已完成')
        return self

class TransferAttachment(Input):
    asset_key: Key
    caption: str = Field(default='', max_length=2000)
    alt_text: str = Field(default='', max_length=2000)
    creator_name: str | None = Field(default=None, max_length=200)

PortableContent = create_model('PortableContent', __base__=Input, **{
    name: (field.annotation, field) for name, field in CardContent.model_fields.items()
    if name not in {'memo_items', 'attachments', 'topic_ids', 'tag_ids', 'taxonomy_mode'}
})

class TransferCard(PortableContent):
    is_bookmarked: bool = Field(default=False, strict=True)
    memo_column_count: int = Field(default=1, ge=1, le=3, strict=True)
    key: Key
    tags: list[str] = Field(default_factory=list, max_length=30)
    lifecycle: Literal['active', 'archived', 'trashed'] = 'active'
    memo_items: list[TransferItem] = Field(default_factory=list, max_length=200)
    attachments: list[TransferAttachment] = Field(default_factory=list, max_length=10)
    link_keys: list[Key] = Field(default_factory=list, max_length=2000)

    @model_validator(mode='after')
    def content(self):
        from app.services.tags import normalize_name
        payload = self.model_dump(exclude={'key','tags','lifecycle','link_keys','memo_items','attachments'})
        payload['memo_items'] = [dict(id=uuid4(), text=i.text, extra_values=i.extra_values, is_completed=i.is_completed) for i in self.memo_items]
        payload['attachments'] = [dict(id=uuid4(), caption=a.caption, alt_text=a.alt_text, creator_name=a.creator_name) for a in self.attachments]
        CardContent.model_validate(payload)
        names = [normalize_name(name) for name in self.tags]
        if len(names) != len(set(names)):
            raise ValueError('标签不能重复')
        self.tags = names
        for values in ([i.key for i in self.memo_items], [a.asset_key for a in self.attachments], self.link_keys, *[i.target_keys for i in self.memo_items]):
            if len(values) != len(set(values)):
                raise ValueError('身份或关联不能重复')
        return self

class TransferAsset(Input):
    key: Key
    path: str = Field(pattern=r'^media/[A-Za-z0-9_-]{1,80}\.(png|jpg|webp)$')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    bytes: int = Field(gt=0, le=20 * 1024 * 1024)
    mime_type: Literal['image/png', 'image/jpeg', 'image/webp']

class ExportInfo(Input):
    generated_at: datetime
    scope: Literal['all-types-all-lifecycles'] = 'all-types-all-lifecycles'
    card_count: int = Field(ge=0)
    excluded: list[str]

class TransferDocument(Input):
    format: Literal['selflore.cards']
    version: Literal[1]
    cards: list[TransferCard] = Field(max_length=MAX_CARDS)
    assets: list[TransferAsset] = Field(default_factory=list, max_length=MAX_MEMBERS - 1)
    export_info: ExportInfo | None = None

    @field_validator('version', mode='before')
    @classmethod
    def version_number(cls, value):
        if isinstance(value, bool):
            raise ValueError('version必须是数字版本号')
        return value
