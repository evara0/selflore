"""Validate a single portable card without persisting it or fetching sources."""
from __future__ import annotations

import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.workspace import CardContent


MAX_IMPORT_BYTES = 1024 * 1024


def invalid(message: str):
    raise HTTPException(422, detail={'code': 'invalid_import', 'message': message})


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'JSON 字段重复：{key}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'JSON 不支持 {value}')


def field_message(issue: dict) -> str:
    kind = issue['type']
    if kind == 'literal_error':
        return '取值不正确，应为 ' + issue.get('ctx', {}).get('expected', '')
    translated = {
        'missing': '缺少必填字段', 'extra_forbidden': '不支持的字段',
        'string_type': '需要文本', 'list_type': '需要数组',
        'model_type': '需要对象', 'int_parsing': '需要整数',
        'bool_parsing': '需要 true 或 false', 'uuid_parsing': '需要有效的 UUID',
        'uuid_type': '需要有效的 UUID',
    }
    if kind in translated:
        return translated[kind]
    if kind in ('string_too_long', 'too_long'):
        return f"内容过长，最多 {issue['ctx']['max_length']} 项或字符"
    if kind in ('string_too_short', 'too_short'):
        return f"内容过短，至少 {issue['ctx']['min_length']} 项或字符"
    return issue['msg'].removeprefix('Value error, ')


def preview(json_text: str) -> dict:
    try:
        size = len(json_text.encode('utf-8'))
    except UnicodeError:
        invalid('JSON 包含无效的 Unicode 字符')
    if size > MAX_IMPORT_BYTES:
        invalid('JSON 内容不能超过 1 MiB')
    try:
        content = json.loads(json_text.lstrip('\ufeff'), object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
    except json.JSONDecodeError as error:
        invalid(f'JSON 格式错误：第 {error.lineno} 行，第 {error.colno} 列')
    except (ValueError, RecursionError) as error:
        invalid('JSON 嵌套过深' if isinstance(error, RecursionError) else str(error))
    if not isinstance(content, dict):
        invalid('请输入一张卡片的 JSON 对象，暂不支持数组或批量导入')
    try:
        json.dumps(content, ensure_ascii=False).encode('utf-8')
    except UnicodeError:
        invalid('JSON 包含无效的 Unicode 字符')
    content.setdefault('taxonomy_mode', 'unified')
    items = content.get('memo_items')
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and 'id' not in item:
                item['id'] = str(uuid4())
    try:
        card = CardContent.model_validate(content)
    except ValidationError as error:
        messages = []
        for issue in error.errors()[:8]:
            field = '.'.join(str(part) for part in issue['loc']) or '内容'
            messages.append(f"{field}：{field_message(issue)}")
        invalid('；'.join(messages))
    return card.model_dump(mode='json')
