from pathlib import Path
from types import SimpleNamespace
import json
import time

from fastapi.testclient import TestClient
import pytest

from app.auth import current_user, get_db, get_settings
from app.main import create_app
from app.services import source_capture as capture, source_http as net


@pytest.mark.parametrize('url', [
    'file:///etc/passwd', 'ftp://example.com/a', 'http://localhost/', 'http://127.0.0.1/',
    'https://[::1]/', 'http://169.254.169.254/latest', 'http://10.0.0.1/',
    'http://user:password@example.com/', 'https://example.com:8080/',
    'https://example.com\\@localhost/', 'https://example.com/\nheader',
    'https://[::ffff:127.0.0.1]/', 'http://224.0.0.1/',
])
def test_reject_unsafe_url(url):
    with pytest.raises(net.FetchError, match='unsafe_url'):
        net.public_url(url)


def test_dns_must_be_all_public(monkeypatch):
    monkeypatch.setattr(net.socket, 'getaddrinfo', lambda *a, **k: [
        (None, None, None, None, ('93.184.215.14', 443)),
        (None, None, None, None, ('192.168.1.2', 443)),
    ])
    with pytest.raises(net.FetchError, match='unsafe_url'):
        net.resolve_public('example.com', 443)


def test_unicode_url_is_encoded_without_double_encoding():
    assert net.public_url('https://example.com/中文?q=标签&next=%2F') == 'https://example.com/%E4%B8%AD%E6%96%87?q=%E6%A0%87%E7%AD%BE&next=%2F'


def install_http(monkeypatch, responses):
    connections, sockets = [], []
    monkeypatch.setattr(net, 'resolve_public', lambda host, port: '93.184.215.14')
    monkeypatch.setattr(net.socket, 'create_connection', lambda address, timeout, source_address: sockets.append(address))

    class Connection:
        def __init__(self, host, port, timeout):
            self.host, self.port = host, port
            self.sock = SimpleNamespace(settimeout=lambda value: None)
            connections.append(self)
        def request(self, method, path, headers):
            self.path, self.headers = path, headers
            self._create_connection((self.host, self.port), 1)
        def getresponse(self):
            return responses.pop(0)
        def close(self):
            pass
    monkeypatch.setattr(net.http.client, 'HTTPSConnection', Connection)
    return connections, sockets


class Response:
    def __init__(self, status=200, headers=None, body=b'<title>Title</title>'):
        self.status, self.headers, self.body = status, headers or {'Content-Type': 'text/html'}, body
    def getheader(self, name, default=None):
        return self.headers.get(name, default)
    def isclosed(self):
        return False
    def read1(self, size):
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


def test_connection_pins_ip_preserves_host_and_sends_no_session(monkeypatch):
    conns, sockets = install_http(monkeypatch, [Response()])
    body, _ = net.fetch('https://example.com/post#fragment', deadline=time.monotonic()+10)
    assert body.startswith(b'<title>')
    assert conns[0].host == 'example.com' and sockets == [('93.184.215.14', 443)]
    assert conns[0].path == '/post'
    assert 'Cookie' not in conns[0].headers and 'Authorization' not in conns[0].headers


@pytest.mark.parametrize('response,code', [
    (Response(302, {'Location': 'http://127.0.0.1/private'}), 'unsafe_url'),
    (Response(302, {'Location': 'http://example.com/plain'}), 'unsafe_url'),
    (Response(403), 'remote_unavailable'),
    (Response(headers={'Content-Type': 'image/png'}), 'unsupported_content'),
    (Response(headers={'Content-Type': 'text/html', 'Content-Encoding': 'gzip'}), 'unsupported_content'),
    (Response(headers={'Content-Type': 'text/html', 'Content-Length': str(net.MAX_BYTES+1)}), 'response_too_large'),
    (Response(body=b'x'*(net.MAX_BYTES+1)), 'response_too_large'),
])
def test_bounded_reader(monkeypatch, response, code):
    conns, _ = install_http(monkeypatch, [response])
    with pytest.raises(net.FetchError, match=code):
        net.fetch('https://example.com', deadline=time.monotonic()+10)
    assert len(conns) == 1


def test_redirect_limit_and_total_deadline(monkeypatch):
    conns, _ = install_http(monkeypatch, [Response(302, {'Location': '/next'}) for _ in range(4)])
    with pytest.raises(net.FetchError, match='redirect_limit'):
        net.fetch('https://example.com', deadline=time.monotonic()+10)
    assert len(conns) == 4
    with pytest.raises(net.FetchError, match='timeout'):
        net.fetch('https://example.com', deadline=time.monotonic()-1)


def test_web_metadata_priority_date_and_no_invented_publisher():
    fields = capture.webpage_fields(b'''<title>Fallback</title><meta property="og:title" content="A &amp; B">
      <meta name="author" content="Jane"><meta property="og:site_name" content="Journal">
      <meta property="article:published_time" content="2026-10-19T12:00:00Z">''', 'text/html')
    assert fields == {'source_title': 'A & B', 'source_author': 'Jane', 'source_platform': 'Journal', 'source_published_on': '2026-10-19'}
    assert capture.webpage_fields(b'<title>Only</title><meta name="citation_publication_date" content="2026-02-30">', 'text/html') == {'source_title': 'Only'}
    with pytest.raises(net.FetchError, match='blocked_page'):
        capture.webpage_fields(b'<title>Just a moment...</title>', 'text/html')


def test_chinese_encoding():
    html = '<meta charset="gbk"><title>中文资料</title>'.encode('gbk')
    assert capture.webpage_fields(html, 'text/html')['source_title'] == '中文资料'


def test_x_adapter_strips_markup_and_uses_free_endpoint(monkeypatch):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return json.dumps({'author_name': 'Author', 'html': '<blockquote><p>Post <a>text</a></p>date<script>evil()</script></blockquote>'}).encode(), 'application/json'
    monkeypatch.setattr(capture, 'fetch', fetch)
    value = capture.resolve('https://x.com/alice/status/123')
    assert value['method'] == 'x_oembed' and value['status'] == 'success'
    assert value['fields'] == {'source_title': 'Post text', 'source_author': 'Author', 'source_platform': 'X'}
    assert calls[0].startswith('https://publish.x.com/oembed?')
    assert 'omit_script=true' in calls[0] and 'dnt=true' in calls[0]


@pytest.mark.parametrize('payload', [None, b'{}', b'invalid', b'[]'])
def test_x_failures_fall_back_to_webpage(monkeypatch, payload):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        if 'oembed?' in url:
            if payload is None:
                raise net.FetchError('timeout')
            return payload, 'application/json'
        return b'<title>Web fallback</title>', 'text/html'
    monkeypatch.setattr(capture, 'fetch', fetch)
    value = capture.resolve('https://twitter.com/alice/status/123')
    assert len(calls) == 2 and value['fallback_reason']
    assert value['method'] == 'webpage' and value['fields']['source_title'] == 'Web fallback'
    assert value['status'] == 'partial'


def test_explicit_webpage_and_x_non_post_skip_oembed(monkeypatch):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        raise net.FetchError('remote_unavailable')
    monkeypatch.setattr(capture, 'fetch', fetch)
    for url, mode in [('https://x.com/alice/status/123', 'webpage'), ('https://x.com/alice', 'auto')]:
        value = capture.resolve(url, mode)
        assert value['method'] == 'webpage' and value['status'] == 'unavailable'
    assert all('oembed' not in url for url in calls)


def test_account_rate_and_busy_limits(monkeypatch):
    monkeypatch.setattr(capture, '_buckets', capture.OrderedDict())
    monkeypatch.setattr(capture, 'resolve', lambda *a: {})
    for _ in range(10):
        capture.limited_resolve('owner', 'https://example.com', 'auto')
    with pytest.raises(net.FetchError, match='rate_limited'):
        capture.limited_resolve('owner', 'https://example.com', 'auto')
    monkeypatch.setattr(capture, '_slots', SimpleNamespace(acquire=lambda **k: False))
    with pytest.raises(net.FetchError, match='busy'):
        capture.limited_resolve('other', 'https://example.com', 'auto')


def test_endpoint_auth_origin_csrf_and_contract(monkeypatch):
    app = create_app(Path('/nonexistent-dist'))
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(origins=('http://testserver',), cookie_name='session')
    calls = []
    def resolve(*args):
        calls.append(args)
        return {'category': 'webpage', 'method': 'webpage', 'status': 'partial', 'fallback_reason': None, 'fields': {'source_title': 'Preview'}}
    monkeypatch.setattr('app.routers.sources.limited_resolve', resolve)
    client = TestClient(app)
    body = {'url': 'https://example.com'}
    assert client.post('/api/sources/resolve', json=body).status_code == 401
    app.dependency_overrides[current_user] = lambda: ('owner', 'test', 'member', True, 'csrf')
    assert client.post('/api/sources/resolve', json=body).status_code == 403
    assert client.post('/api/sources/resolve', json=body, headers={'Origin': 'http://testserver'}).status_code == 403
    assert not calls
    response = client.post('/api/sources/resolve', json=body, headers={'Origin': 'http://testserver', 'X-CSRF-Token': 'csrf'})
    assert response.status_code == 200 and response.json()['fields'] == {'source_title': 'Preview'}
    assert calls == [('owner', 'https://example.com', 'auto')]


def test_new_platform_adapter_reuses_routing_and_fallback(monkeypatch):
    monkeypatch.setattr(capture, 'ADAPTERS', (capture.SourceAdapter(
        'fixture', frozenset({'example.com'}), r'/post/[0-9]+', 'fixture_metadata',
        lambda url, deadline: {'source_title': 'Future source', 'source_author': 'Author'}),))
    value = capture.resolve('https://example.com/post/123')
    assert value['category'] == 'fixture' and value['method'] == 'fixture_metadata'


def test_network_timeout_is_safe(monkeypatch):
    install_http(monkeypatch, [])
    def timeout(*args, **kwargs):
        raise TimeoutError('private network details')
    monkeypatch.setattr(net, 'resolve_public', timeout)
    with pytest.raises(net.FetchError, match='^timeout$'):
        net.fetch('https://example.com', deadline=time.monotonic()+10)
