"""Platform adapters return suggestions only, never HTML or persisted card changes."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from email.message import Message
from html.parser import HTMLParser
import json
import re
import threading
import time
from typing import Callable
from urllib.parse import urlencode, urlsplit

from app.services.source_http import FetchError, fetch, public_url

X_HOSTS = {'x.com', 'www.x.com', 'mobile.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com'}
_slots = threading.BoundedSemaphore(3)
_lock = threading.Lock()
_buckets = OrderedDict()


def clean(value, limit=200):
    if not isinstance(value, str):
        return ''
    return ' '.join(''.join(c for c in value if c.isprintable() or c.isspace()).split())[:limit]


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = []
        self.paragraph = []
        self._title = False
        self._paragraph = False
        self._paragraph_done = False
        self._hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self._hidden += 1
        if tag == 'title':
            self._title = True
        if tag == 'p' and not self._paragraph_done:
            self._paragraph = True
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            content = attrs.get('content') or ''
            if content and key not in self.meta:
                self.meta[key] = content

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._hidden = max(0, self._hidden - 1)
        if tag == 'title':
            self._title = False
        if tag == 'p' and self._paragraph:
            self._paragraph = False
            self._paragraph_done = True

    def handle_data(self, data):
        if not self._hidden:
            if self._title:
                self.title.append(data)
            if self._paragraph:
                self.paragraph.append(data)


def webpage_fields(raw: bytes, content_type: str):
    message = Message()
    message['content-type'] = content_type
    encoding = message.get_content_charset() or 'utf-8'
    # Older Chinese pages may declare encoding only in the HTML head.
    if not message.get_content_charset():
        match = re.search(br'<meta\b[^>]*charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', raw[:8192], re.I)
        if match:
            encoding = match[1].decode('ascii')
    try:
        html = raw.decode(encoding, errors='replace')
    except LookupError:
        html = raw.decode('utf-8', errors='replace')
    parser = Metadata()
    parser.feed(html)
    meta = parser.meta
    title = clean(meta.get('og:title') or meta.get('twitter:title') or ''.join(parser.title))
    if re.search(r'^(just a moment|access denied|security check|attention required|verify you are human|请完成安全验证)', title, re.I):
        raise FetchError('blocked_page')
    fields = {
        'source_title': title,
        'source_author': clean(meta.get('author') or meta.get('citation_author')),
        'source_publisher': clean(meta.get('citation_publisher') or meta.get('publisher')),
        'source_platform': clean(meta.get('og:site_name') or meta.get('application-name'), 80),
    }
    published = clean(meta.get('article:published_time') or meta.get('citation_publication_date'))
    try:
        fields['source_published_on'] = date.fromisoformat(published[:10].replace('/', '-')).isoformat()
    except ValueError:
        pass
    return {key: value for key, value in fields.items() if value}


def x_fields(url: str, deadline: float):
    endpoint = 'https://publish.x.com/oembed?' + urlencode({'url': url, 'omit_script': 'true', 'dnt': 'true'})
    raw, _ = fetch(endpoint, deadline=min(deadline, time.monotonic() + 6), accept='application/json')
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        parser = Metadata()
        parser.feed(value.get('html', '') if isinstance(value.get('html'), str) else '')
        fields = {'source_title': clean(''.join(parser.paragraph)),
                  'source_author': clean(value.get('author_name')), 'source_platform': 'X'}
        if not fields['source_title'] and not fields['source_author']:
            raise FetchError('empty_metadata')
        return {key: val for key, val in fields.items() if val}
    except (ValueError, UnicodeError, RecursionError):
        raise FetchError('invalid_response') from None


@dataclass(frozen=True)
class SourceAdapter:
    category: str
    hosts: frozenset[str]
    path_pattern: str
    method: str
    extract: Callable[[str, float], dict]


ADAPTERS = (SourceAdapter('x', frozenset(X_HOSTS),
                         r'/(?:[A-Za-z0-9_]+/status|i/web/status)/[0-9]+(?:/.*)?',
                         'x_oembed', x_fields),)


def resolve(url: str, mode='auto'):
    url = public_url(url.strip())
    parts = urlsplit(url)
    adapter = next((item for item in ADAPTERS if parts.hostname in item.hosts), None)
    category = adapter.category if adapter else 'webpage'
    deadline = time.monotonic() + 18
    fallback = None
    if adapter and mode == 'auto':
        if re.fullmatch(adapter.path_pattern, parts.path):
            try:
                fields = adapter.extract(url, deadline)
                return result(category, adapter.method, fields, None)
            except FetchError as exc:
                fallback = str(exc)
        else:
            fallback = 'not_post_url'
    try:
        raw, content_type = fetch(url, deadline=deadline)
        fields = webpage_fields(raw, content_type)
        return result(category, 'webpage', fields, fallback)
    except FetchError as exc:
        return {**result(category, 'webpage', {}, fallback), 'error': str(exc)}


def result(category, method, fields, fallback):
    # Success means a useful title and author, not a claim that all provenance is known.
    status = 'success' if fields.get('source_title') and fields.get('source_author') else 'partial' if fields else 'unavailable'
    return {'category': category, 'method': method, 'status': status,
            'fallback_reason': fallback, 'fields': fields}


def limited_resolve(owner, url, mode):
    now = time.monotonic()
    with _lock:
        while _buckets and next(iter(_buckets.values()))[0] < now - 60:
            _buckets.popitem(last=False)
        start, count = _buckets.get(owner, (now, 0))
        if count >= 10 or (owner not in _buckets and len(_buckets) >= 4096):
            raise FetchError('rate_limited')
        _buckets[owner] = (start, count + 1)
    if not _slots.acquire(blocking=False):
        raise FetchError('busy')
    try:
        return resolve(url, mode)
    finally:
        _slots.release()
