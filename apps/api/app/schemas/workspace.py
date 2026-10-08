from __future__ import annotations

from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CardContent(Input):
    kind: Literal['knowledge', 'opinion']
    form: Literal['qa', 'cloze'] | None = None
    title: str = Field(min_length=1, max_length=200)
    question_md: str | None = None
    answer_md: str | None = None
    body_md: str | None = None
    source_title: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    source_locator: str | None = Field(default=None, max_length=200)
    topic_ids: list[UUID] = Field(default_factory=list, max_length=10)
    tag_ids: list[UUID] = Field(default_factory=list, max_length=20)
    processing_state: Literal['inbox', 'organized'] = 'inbox'
    is_bookmarked: bool = False

    @field_validator('question_md', 'answer_md', 'body_md')
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
        if len(set(self.topic_ids)) != len(self.topic_ids) or len(set(self.tag_ids)) != len(self.tag_ids):
            raise ValueError('分类或标签不能重复')
        if self.kind == 'opinion':
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
        if self.kind == 'knowledge' and len(self.topic_ids) > 1:
            raise ValueError('知识最多一个分类')
        return self


class CardCreate(CardContent):
    client_request_id: UUID


class CardPatch(Input):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    question_md: str | None = None
    answer_md: str | None = None
    body_md: str | None = None
    source_title: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    source_locator: str | None = Field(default=None, max_length=200)
    topic_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    processing_state: Literal['inbox', 'organized'] | None = None
    is_bookmarked: bool | None = None


class Revision(Input):
    expected_revision: int = Field(ge=1)


class Lifecycle(Revision):
    action: Literal['archive', 'trash', 'restore']


class TaxonomyCreate(Input):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['knowledge', 'opinion'] | None = None


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
