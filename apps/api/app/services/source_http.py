"""Small public-network reader. Never use a proxy, browser session or unpinned DNS."""
from __future__ import annotations

import http.client
import ipaddress
import socket
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

MAX_BYTES = 1024 * 1024
NETWORK_TIMEOUT = 6


class FetchError(Exception):
    """Safe machine-readable failure; never return underlying network exceptions."""


def public_url(value: str) -> str:
    if len(value) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in value) or '\\' in value:
        raise FetchError('unsafe_url')
    try:
        parts = urlsplit(value)
        host = (parts.hostname or '').encode('idna').decode('ascii').lower()
        port = parts.port
    except (ValueError, UnicodeError):
        raise FetchError('unsafe_url') from None
    if (parts.scheme not in ('https', 'http') or not host or '%' in host
            or parts.username is not None or parts.password is not None
            or port not in (None, 443 if parts.scheme == 'https' else 80)
            or host.rstrip('.').endswith(('.localhost', '.local')) or host.rstrip('.') == 'localhost'):
        raise FetchError('unsafe_url')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not is_public(address):
            raise FetchError('unsafe_url')
    netloc = f'[{host}]' if ':' in host else host
    return urlunsplit((parts.scheme, netloc, quote(parts.path or '/', safe="/:@!$&'()*+,;=-._~%"),
                      quote(parts.query, safe="=&?/:@!$'()*+,;[]-._~%"), ''))


def is_public(address):
    return address.is_global and not address.is_multicast and not address.is_reserved and not (
        isinstance(address, ipaddress.IPv6Address) and
        (address.ipv4_mapped or address.sixtofour or address.teredo)
    )


def resolve_public(host: str, port: int) -> str:
    rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = [row[4][0] for row in rows]
    if not addresses or any(not is_public(ipaddress.ip_address(ip)) for ip in addresses):
        raise FetchError('unsafe_url')
    return addresses[0]


def remaining(deadline: float) -> float:
    value = min(NETWORK_TIMEOUT, deadline - time.monotonic())
    if value <= 0:
        raise FetchError('timeout')
    return value


def stop_reading(wire):
    try:
        wire.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def fetch(url: str, *, deadline: float, accept: str = 'text/html') -> tuple[bytes, str]:
    """Follow at most 3 redirects, checking and pinning every connection separately."""
    for hop in range(4):
        url = public_url(url)
        parts = urlsplit(url)
        port = 443 if parts.scheme == 'https' else 80
        connection = None
        timer = None
        try:
            remaining(deadline)
            ip = resolve_public(parts.hostname, port)
            factory = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
            connection = factory(parts.hostname, port, timeout=remaining(deadline))
            # HTTPSConnection still wraps with the original hostname for SNI and verification.
            connection._create_connection = lambda address, timeout, source_address=None: socket.create_connection(
                (ip, port), timeout, source_address
            )
            path = urlunsplit(('', '', parts.path or '/', parts.query, ''))
            connection.request('GET', path, headers={
                'User-Agent': 'SelfLore-LinkPreview/1.0', 'Accept': accept,
                'Accept-Encoding': 'identity', 'Connection': 'close',
            })
            wire = connection.sock
            wire.settimeout(remaining(deadline))
            # Interrupt this exact socket even when headers arrive a byte at a time.
            timer = threading.Timer(max(0.001, deadline - time.monotonic()), stop_reading, (wire,))
            timer.daemon = True
            timer.start()
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if hop == 3 or not location:
                    raise FetchError('redirect_limit')
                next_url = public_url(urljoin(url, location))
                if parts.scheme == 'https' and urlsplit(next_url).scheme != 'https':
                    raise FetchError('unsafe_url')
                url = next_url
                continue
            if response.status != 200:
                raise FetchError('remote_unavailable')
            content_type = response.getheader('Content-Type', '')
            mime = content_type.split(';')[0].strip().lower()
            allowed = ('application/json',) if accept == 'application/json' else ('text/html', 'application/xhtml+xml')
            if mime not in allowed or response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise FetchError('unsupported_content')
            length = response.getheader('Content-Length')
            if length and (not length.isdigit() or int(length) > MAX_BYTES):
                raise FetchError('response_too_large')
            chunks, size = [], 0
            while True:
                # read1 returns after a socket read; the total deadline is checked each time.
                if response.isclosed():
                    break
                wire.settimeout(remaining(deadline))
                chunk = response.read1(min(16384, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FetchError('response_too_large')
                chunks.append(chunk)
            remaining(deadline)
            return b''.join(chunks), content_type
        except FetchError:
            raise
        except (TimeoutError, socket.timeout):
            raise FetchError('timeout') from None
        except (OSError, ValueError, http.client.HTTPException):
            raise FetchError('timeout' if time.monotonic() >= deadline else 'remote_unavailable') from None
        finally:
            if timer:
                timer.cancel()
            if connection:
                connection.close()
    raise FetchError('redirect_limit')
