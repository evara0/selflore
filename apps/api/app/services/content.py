"""Markdown-aware cloze and stable-reference parsing; no HTML interpretation."""
from __future__ import annotations

import re
from uuid import UUID

CODE = re.compile(r'```[^\n]*\n[\s\S]*?(?:```|$)|~~~[^\n]*\n[\s\S]*?(?:~~~|$)|`+[^`]*`+')
CLOZE = re.compile(r'\{\{c([1-9][0-9]?)::([^{}]*?)\}\}')
REFERENCE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]*))?\]\]')


def prose(text: str) -> str:
    return CODE.sub(lambda match: ' ' * len(match.group()), text)


def cloze_indices(text: str) -> list[int]:
    clean = prose(text)
    found = list(CLOZE.finditer(clean))
    if not found or len({int(m[1]) for m in found})>20:
        raise ValueError('填空需包含 1–20 个有效编号，如 {{c1::答案::提示}}')
    for match in found:
        if not match[2].split('::',1)[0].strip():
            raise ValueError('填空答案不能为空')
    if '{{' in CLOZE.sub('',clean) or '}}' in CLOZE.sub('',clean):
        raise ValueError('填空语法错误或不支持嵌套')
    return sorted({int(match[1]) for match in found})


def references(text: str) -> set[UUID]:
    result = set()
    for match in REFERENCE.finditer(prose(text)):
        try:
            result.add(UUID(match[1]))
        except ValueError:
            # A title alone is unresolved, never bound arbitrarily.
            if match[2] is not None:
                raise ValueError('稳定引用必须使用有效的卡片 UUID') from None
    return result


def cloze_text(text: str, index: int | None, reveal: bool) -> str:
    clean = prose(text)
    matches = list(CLOZE.finditer(clean))
    for match in reversed(matches):
        answer, _, hint = match[2].partition('::')
        value = answer if reveal or (index is not None and int(match[1]) != index) else f'【{hint or "…"}】'
        text = text[:match.start()] + value + text[match.end():]
    return text
