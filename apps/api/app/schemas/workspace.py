from __future__ import annotations

from typing import Literal
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class AttachmentLink(Input):
    id: UUID
    caption: str = Field(default='', max_length=2000)
    alt_text: str = Field(default='', max_length=2000)
    creator_name: str | None = Field(default=None, max_length=200)


class MemoItem(Input):
    id: UUID
    text: str = Field(min_length=1, max_length=2000)
    extra_values: list[str] = Field(default_factory=lambda: ['', ''], min_length=2, max_length=2)
    is_completed: bool = False
    target_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator('extra_values')
    @classmethod
    def valid_values(cls, value):
        if any(len(v)>2000 for v in value):
            raise ValueError('每个字段最多2000字符')
        return value

    @field_validator('target_ids')
    @classmethod
    def unique_targets(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('关联不能重复')
        return value


class CardContent(Input):
    kind: Literal['knowledge', 'opinion', 'reference', 'memo']
    memo_format: Literal['note', 'checklist'] | None = None
    memo_columns: list[str] = Field(default_factory=lambda: ['条目', '字段 2', '字段 3'], min_length=3, max_length=3)
    memo_column_count: int = Field(default=1, ge=1, le=3)
    memo_items: list[MemoItem] = Field(default_factory=list, max_length=200)
    form: Literal['qa', 'cloze'] | None = None
    title: str = Field(min_length=1, max_length=200)
    question_md: str | None = None
    answer_md: str | None = None
    body_md: str | None = None
    note_md: str | None = None
    attachments: list[AttachmentLink] = Field(default_factory=list, max_length=10)
    source_author: str | None = Field(default=None, max_length=200)
    source_publisher: str | None = Field(default=None, max_length=200)
    source_platform: str | None = Field(default=None, max_length=80)
    source_published_on: date | None = None
    source_title: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    source_locator: str | None = Field(default=None, max_length=200)
    topic_ids: list[UUID] = Field(default_factory=list, max_length=10)
    tag_ids: list[UUID] = Field(default_factory=list, max_length=30)
    taxonomy_mode: Literal['unified'] | None = None
    processing_state: Literal['inbox', 'organized'] = 'inbox'
    is_bookmarked: bool = False

    @field_validator('memo_columns')
    @classmethod
    def valid_columns(cls, value):
        if any(not v.strip() or len(v.strip())>40 for v in value):
            raise ValueError('列名需要1–40字符')
        return [v.strip() for v in value]

    @field_validator('question_md', 'answer_md', 'body_md', 'note_md')
    @classmethod
    def markdown_size(cls, value):
        if value is not None and len(value.encode('utf-8')) > 65536:
            raise ValueError('正文最多 64 KiB')
        return value

    @field_validator('source_url')
    @classmethod
    def safe_url(cls, value):
        if value and not value.startswith(('https://', 'http://')):
            raise ValueError('来源仅支持 HTTP 或 HTTPS')
        return value or None

    @model_validator(mode='after')
    def valid_content(self):
        if self.taxonomy_mode == 'unified' and self.topic_ids:
            raise ValueError('统一标签模式不接收分类')
        if len(set(self.tag_ids))!=len(self.tag_ids): raise ValueError('标签不能重复')
        if self.kind == 'memo':
            if self.memo_format is None or self.form is not None or self.question_md is not None or self.answer_md is not None or self.note_md is not None or self.attachments or self.topic_ids:
                raise ValueError('备忘形式或内容不合法')
            if (self.memo_format == 'checklist') != bool(self.memo_items):
                raise ValueError('清单至少一项，普通备忘不使用条目')
            if len({item.id for item in self.memo_items}) != len(self.memo_items):
                raise ValueError('条目不能重复')
            return self
        if self.memo_format is not None or self.memo_items:
            raise ValueError('只有备忘支持条目和备忘形式')
        if len(set(self.topic_ids)) != len(self.topic_ids) or len(set(self.tag_ids)) != len(self.tag_ids):
            raise ValueError('分类或标签不能重复')
        if len({item.id for item in self.attachments}) != len(self.attachments):
            raise ValueError('图片不能重复')
        if self.kind != 'reference' and (self.attachments or self.note_md is not None):
            raise ValueError('只有资料支持图片及个人说明')
        if self.kind == 'reference':
            if self.form is not None or self.question_md is not None or self.answer_md is not None:
                raise ValueError('资料不使用问题和答案')
            if not self.body_md and not self.attachments:
                raise ValueError('资料需要原始摘录或完成图片')
        elif self.kind == 'opinion':
            if self.form is not None or not self.body_md or self.question_md is not None or self.answer_md is not None:
                raise ValueError('观点需要独立正文')
        elif self.form == 'qa':
            if not self.question_md or not self.answer_md or self.body_md is not None:
                raise ValueError('问答需要问题和答案')
        elif self.form == 'cloze':
            if not self.body_md or self.question_md is not None or self.answer_md is not None:
                raise ValueError('填空需要正文')
            from app.services.content import cloze_indices
            cloze_indices(self.body_md)
        else:
            raise ValueError('知识需要问答或填空形式')
        if self.kind in ('knowledge', 'reference') and len(self.topic_ids) > 1:
            raise ValueError('知识或资料最多一个分类')
        return self


class CardCreate(CardContent):
    client_request_id: UUID


class CardPatch(Input):
    expected_revision: int = Field(ge=1)
    taxonomy_mode: Literal['unified'] | None = None
    memo_items: list[MemoItem] | None = Field(default=None, max_length=200)
    memo_columns: list[str] | None = None
    memo_column_count: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    question_md: str | None = None
    answer_md: str | None = None
    body_md: str | None = None
    note_md: str | None = None
    attachments: list[AttachmentLink] | None = Field(default=None, max_length=10)
    source_author: str | None = Field(default=None, max_length=200)
    source_publisher: str | None = Field(default=None, max_length=200)
    source_platform: str | None = Field(default=None, max_length=80)
    source_published_on: date | None = None
    source_title: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    source_locator: str | None = Field(default=None, max_length=200)
    topic_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    processing_state: Literal['inbox', 'organized'] | None = None
    is_bookmarked: bool | None = None


class MemoCompletion(Input):
    expected_revision: int = Field(ge=1)
    is_completed: bool


class MemoOrder(Input):
    expected_revision: int = Field(ge=1)
    item_ids: list[UUID] = Field(min_length=1, max_length=200)


class Revision(Input):
    expected_revision: int = Field(ge=1)


class Lifecycle(Revision):
    action: Literal['archive', 'trash', 'restore']


class TaxonomyCreate(Input):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['knowledge', 'opinion', 'reference'] | None = None


class TaxonomyPatch(Input):
    name: str = Field(min_length=1, max_length=80)


class CollectionContent(Input):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field(default='', max_length=65536)
    cover_style: Literal['curve', 'lines', 'radial'] = 'curve'
    cover_color: Literal['sage', 'clay'] = 'sage'
    is_favorite: bool = False
    is_pinned: bool = False

    @field_validator('description_md')
    @classmethod
    def byte_size(cls, value):
        if len(value.encode('utf-8')) > 65536:
            raise ValueError('说明最多 64 KiB')
        return value


class CollectionCreate(CollectionContent):
    client_request_id: UUID


class CollectionPatch(Revision):
    title: str | None = None
    description_md: str | None = None
    cover_style: Literal['curve', 'lines', 'radial'] | None = None
    cover_color: Literal['sage', 'clay'] | None = None
    is_favorite: bool | None = None
    is_pinned: bool | None = None


class Members(Revision):
    card_ids: list[UUID] = Field(min_length=1, max_length=100)


class Order(Revision):
    item_ids: list[UUID] = Field(max_length=10000)


class RatingInput(Input):
    request_id: UUID
    rating: int = Field(ge=1, le=4)
    expected_state_version: int = Field(ge=1)
    expected_content_revision: int = Field(ge=1)
    duration_ms: int = Field(default=0, ge=0, le=3600000)


class ProfilePatch(Revision):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=2000)
    avatar_color: Literal['sage', 'clay', 'ink'] | None = None
    interests: list[str] | None = Field(default=None, max_length=8)
    timezone: str | None = Field(default=None, max_length=64)
    daily_new_limit: int | None = Field(default=None, ge=0, le=100)
    daily_review_goal: int | None = Field(default=None, ge=1, le=1000)

    @field_validator('timezone')
    @classmethod
    def known_timezone(cls, value):
        if value is not None:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError('请选择有效的 IANA 时区') from None
        return value

    @field_validator('interests')
    @classmethod
    def interest_names(cls, value):
        if value is not None and any(not item.strip() or len(item)>32 for item in value):
            raise ValueError('兴趣标签需为 1–32 个字符')
        return list(dict.fromkeys(item.strip() for item in value)) if value is not None else None
