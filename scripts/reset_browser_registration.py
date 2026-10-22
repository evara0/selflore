"""Reset only the loopback registration bucket in an explicit disposable test DB."""
from __future__ import annotations

import hashlib
import hmac
import os


def checked_target(info):
    expected = dict(host='127.0.0.1', port='6179', dbname='selflore_dev', user='selflore_dev_app')
    if any(info.get(key) != value for key, value in expected.items()):
        raise RuntimeError('browser reset requires the fixed disposable app database')
    if set(info) - set(expected) - {'password', 'connect_timeout'}:
        raise RuntimeError('browser reset rejects connection overrides')
    return expected


def reset(environ=None, *, parse=None, connect=None):
    env = os.environ if environ is None else environ
    dsn = env.get('SELFLORE_TEST_APP_DSN')
    if env.get('SELFLORE_TEST_ISOLATED') != '1' or not dsn:
        raise RuntimeError('browser reset requires explicit disposable environment and app DSN')
    if parse is None or connect is None:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        parse, connect = conninfo_to_dict, psycopg.connect
    try:
        info = parse(dsn)
    except Exception:
        raise RuntimeError('invalid browser test DSN') from None
    target = checked_target(info)
    key = (env.get('SELFLORE_THROTTLE_KEY') or 'selflore-local-development-only').encode()
    bucket = hmac.new(key, b'register-ip:127.0.0.1', hashlib.sha256).hexdigest()
    with connect(**target, password=info.get('password', env.get('SELFLORE_APP_PASSWORD', '')),
                 connect_timeout=5, passfile=os.devnull, sslmode='disable') as db:
        if db.execute('SELECT current_database(), current_user').fetchone() != ('selflore_dev', 'selflore_dev_app'):
            raise RuntimeError('browser test database identity differs')
        db.execute('DELETE FROM app.auth_login_throttle WHERE bucket_key = %s', (bucket,))


if __name__ == '__main__':
    try:
        reset()
    except Exception:
        # Connection errors can contain credentials; never print them.
        raise SystemExit('Disposable browser registration reset failed; check isolation and test DSN.')
