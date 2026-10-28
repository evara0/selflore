"""Loopback-only browser fixture: real import validation, no business database.

Started and stopped by json-import.spec.ts. It cannot persist cards or connect to
an inherited application database; browser writes are handled in test memory.
"""
from pathlib import Path
import os
import socket
import sys
from types import SimpleNamespace
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import current_user, get_db, get_settings
from app.main import create_app
import uvicorn


def build_fixture():
    if os.environ.get('SELFLORE_DATABASE_URL'):
        raise RuntimeError('Preview fixture refuses an application database connection')
    app = create_app(Path('/nonexistent-dist'))
    def no_database():
        raise RuntimeError('Preview fixture cannot access a business database')
    app.dependency_overrides[get_db] = no_database
    app.dependency_overrides[current_user] = lambda: (UUID(int=900), 'fixture', 'member', True, 'synthetic')
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(origins=('http://import.test',), cookie_name='session')
    return app


if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        print(f'IMPORT_PREVIEW_PORT={listener.getsockname()[1]}', flush=True)
        server = uvicorn.Server(uvicorn.Config(build_fixture(), log_level='error', access_log=False))
        server.run(sockets=[listener])
