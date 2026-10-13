"""Immutable file inventory used with a database snapshot, never a directory dump."""
from __future__ import annotations
import shutil
from pathlib import Path
from app.media_storage import MediaError,safe_path,file_hash,MediaConfig


def validate_media(root: Path, entries: list[dict]):
    seen=set()
    for entry in entries:
        for variant in ('original','thumbnail'):
            key=entry[variant+'_key']
            if key in seen: raise MediaError('附件包含重复文件键')
            seen.add(key); path=safe_path(root,key)
            if not path.is_file() or path.stat().st_size!=entry[variant+'_bytes'] or file_hash(path)!=entry[variant+'_sha256']:
                raise MediaError('附件文件缺失或校验不符')


def pack_media(config: MediaConfig, entries: list[dict], bundle: Path):
    if not entries: return
    root=config.check()
    if bundle.resolve().is_relative_to(root.resolve()) or (config.ops_root and bundle.resolve().is_relative_to(config.ops_root.resolve())):
        raise MediaError('备份目标不能位于媒体或运维源目录')
    validate_media(root,entries)
    target=bundle/'media'; target.mkdir()
    for entry in entries:
        for variant in ('original','thumbnail'):
            key=entry[variant+'_key']; destination=safe_path(target,key)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe_path(root,key),destination)
    validate_media(target,entries)


def restore_media(bundle: Path, entries: list[dict], target: Path):
    if target.exists(): raise MediaError('演练媒体目标已存在，拒绝覆盖')
    source=bundle/'media'
    if entries: validate_media(source,entries)
    target.mkdir()
    for entry in entries:
        for variant in ('original','thumbnail'):
            key=entry[variant+'_key']; destination=safe_path(target,key)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe_path(source,key),destination)
    if entries: validate_media(target,entries)
