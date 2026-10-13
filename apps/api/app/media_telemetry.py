"""Bounded, content-free request telemetry and cross-platform file locking."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import threading
import time
from uuid import uuid4

from starlette.responses import JSONResponse
from app.media_storage import MediaConfig,MediaError,safe_path

_thread_lock=threading.RLock()
MAX_LOG_BYTES=5*1024*1024
LOG_FILES=6


@contextmanager
def telemetry_lock(root: Path, *, readonly=False):
    lock=safe_path(root,'telemetry.lock')
    with _thread_lock, lock.open('rb' if readonly else 'r+b') as stream:
        deadline=time.monotonic()+2
        while True:
            try:
                stream.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBRLCK if readonly else msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),(fcntl.LOCK_SH if readonly else fcntl.LOCK_EX)|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>=deadline: raise MediaError('遥测锁暂不可用') from None
                time.sleep(0.02)
        try: yield
        finally:
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def append_event(config,event):
    root=config.check(ops=True)
    payload=(json.dumps(event,separators=(',',':'))+'\n').encode()
    with telemetry_lock(root):
        path=safe_path(root,'media-requests.jsonl')
        if path.exists() and path.stat().st_size+len(payload)>MAX_LOG_BYTES:
            oldest=safe_path(root,f'media-requests.{LOG_FILES-1}.jsonl')
            if oldest.exists(): oldest.unlink()
            for n in range(LOG_FILES-2,0,-1):
                previous=safe_path(root,f'media-requests.{n}.jsonl')
                if previous.exists(): previous.replace(safe_path(root,f'media-requests.{n+1}.jsonl'))
            path.replace(safe_path(root,'media-requests.1.jsonl'))
        with path.open('ab') as stream: stream.write(payload)


def read_events(config):
    root=config.check(ops=True); events=[]
    with telemetry_lock(root,readonly=True):
        paths=[safe_path(root,'media-requests.jsonl')]+[safe_path(root,f'media-requests.{n}.jsonl') for n in range(1,LOG_FILES)]
        for path in paths:
            if path.is_file():
                for line in path.read_text(encoding='utf-8').splitlines():
                    try: events.append(json.loads(line))
                    except ValueError: raise MediaError('遥测记录损坏') from None
    return events


class MediaTelemetry:
    def __init__(self,app):
        self.app=app; self.instance=uuid4().hex; self.started=False

    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        if scope['type']!='http' or not path.startswith('/api/attachments'):
            return await self.app(scope,receive,send)
        category='upload' if path=='/api/attachments' and scope['method']=='POST' else None
        if re.fullmatch(r'/api/attachments/[0-9a-f-]{36}/content',path):
            from urllib.parse import parse_qs
            category='original' if parse_qs(scope.get('query_string',b'').decode()).get('variant')==['original'] else 'thumbnail'
        if category is None: return await self.app(scope,receive,send)
        try: config=MediaConfig.load()
        except MediaError: config=None
        start=time.monotonic(); bytes_sent=0; status=500; complete=False; received=0
        max_body=(config.max_bytes if config else 20*1024*1024)+1024*1024
        headers=dict(scope.get('headers',[]))
        async def guard():
            nonlocal received
            message=await receive()
            if message['type']=='http.request':
                received+=len(message.get('body',b''))
                if category=='upload' and received>max_body:
                    raise MediaError('上传请求超过大小限制')
            return message
        async def counted(message):
            nonlocal bytes_sent,status,complete
            if message['type']=='http.response.start': status=message['status']
            if message['type']=='http.response.body': bytes_sent+=len(message.get('body',b''))
            await send(message)
            if message['type']=='http.response.body' and not message.get('more_body',False): complete=True
        try:
            if category=='upload' and int(headers.get(b'content-length',b'0'))>max_body:
                await JSONResponse({'detail':{'code':'image_too_large','message':'上传请求超过大小限制'}},status_code=413)(scope,receive,counted)
            else:
                await self.app(scope,guard,counted)
        finally:
            if config:
                try:
                    now=datetime.now(timezone.utc).isoformat()
                    if not self.started:
                        append_event(config,{'time':now,'instance':self.instance,'category':'start'})
                        self.started=True
                    append_event(config,{'time':now,'instance':self.instance,'category':category,'status':status,
                                         'bytes':bytes_sent,'elapsed_ms':round((time.monotonic()-start)*1000,3),
                                         'result':'complete' if complete else 'interrupted'})
                except (OSError,MediaError): pass
