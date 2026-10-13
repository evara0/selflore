"""Private, explicitly initialized local media; no startup directory creation."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
import argparse

MARKER = '.selflore-media.json'


def load_media_environment(path: Path) -> None:
    """Load only nonsecret media settings, leaving backup connection identity untouched."""
    if not path.is_file(): return
    for line in path.read_text(encoding='utf-8').splitlines():
        name,sep,value=line.strip().partition('=')
        if sep and name.startswith('SELFLORE_MEDIA_'):
            os.environ.setdefault(name,value.strip().strip('"\''))


class MediaError(Exception):
    pass


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def safe_path(root: Path, key: str) -> Path:
    parts = PurePosixPath(key).parts
    if not key or '\\' in key or ':' in key or key.startswith('/') or any(p in ('..', '.') for p in key.split('/')):
        raise MediaError('媒体路径不合法')
    if not root.is_absolute() or not root.is_dir() or linked(root):
        raise MediaError('媒体根目录不存在或为链接')
    # Check every existing ancestor, including root ancestors, before resolving.
    for parent in (root, *root.parents):
        if linked(parent):
            raise MediaError('媒体目录不能经过链接或重解析点')
    path = root
    for part in parts:
        path = path / part
        if path.exists() or path.is_symlink():
            if linked(path):
                raise MediaError('媒体路径不能经过链接或重解析点')
    if not path.resolve().is_relative_to(root.resolve()):
        raise MediaError('媒体路径越界')
    return path


def positive_setting(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
        if value < 1:
            raise ValueError()
        return value
    except ValueError:
        raise MediaError(f'{name}必须为正整数') from None


@dataclass
class MediaConfig:
    root: Path | None
    ops_root: Path | None
    environment: str
    database: str
    max_bytes: int = 20 * 1024 * 1024
    max_pixels: int = 40_000_000
    max_edge: int = 20000
    max_images: int = 10

    @classmethod
    def load(cls):
        env = os.environ.get('SELFLORE_ENV', 'dev')
        if env not in ('dev', 'prod'):
            raise MediaError('媒体环境不合法')
        return cls(Path(os.environ['SELFLORE_MEDIA_ROOT']) if os.environ.get('SELFLORE_MEDIA_ROOT') else None,
                   Path(os.environ['SELFLORE_MEDIA_OPS_ROOT']) if os.environ.get('SELFLORE_MEDIA_OPS_ROOT') else None,
                   env, f'selflore_{env}',
                   positive_setting('SELFLORE_MEDIA_MAX_BYTES', 20 * 1024 * 1024),
                   positive_setting('SELFLORE_MEDIA_MAX_PIXELS', 40_000_000),
                   positive_setting('SELFLORE_MEDIA_MAX_EDGE', 20000))

    def check(self, *, ops: bool = False) -> Path:
        root = self.ops_root if ops else self.root
        if root is None:
            raise MediaError('图片存储未配置，请显式配置媒体及运维目录')
        marker = safe_path(root, MARKER)
        try:
            identity = json.loads(marker.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise MediaError('媒体目录标识缺失或无法读取，请核对显式初始化配置') from None
        if identity != {'environment': self.environment, 'database': self.database, 'kind': 'ops' if ops else 'media'}:
            raise MediaError('媒体目录的环境或数据库标识不符')
        return root

    def limits(self) -> dict:
        return {'max_bytes': self.max_bytes, 'max_pixels': self.max_pixels, 'max_edge': self.max_edge,
                'max_images': self.max_images, 'formats': ['image/jpeg', 'image/png', 'image/webp']}


def initialize(config: MediaConfig) -> None:
    from app.local_start import PROJECT_DIR, protect_directory
    roots = [config.root, config.ops_root]
    if any(root is None or not root.is_absolute() for root in roots):
        raise MediaError('显式初始化需要两个绝对目录')
    media, ops = (root.resolve() for root in roots)
    if media == ops or media.is_relative_to(ops) or ops.is_relative_to(media):
        raise MediaError('媒体和运维目录不能重叠')
    for root in roots:
        if root.resolve().is_relative_to(PROJECT_DIR.resolve()) and '.cache' not in root.parts:
            raise MediaError('业务媒体必须在项目与发布目录外；隔离测试可使用.cache')
        for ancestor in (root, *root.parents):
            if ancestor.exists() and linked(ancestor):
                raise MediaError('初始化路径不能经过链接')
        if root.exists() and any(root.iterdir()):
            # An initialized directory can be rechecked, never rewrite another identity or ACL.
            config.check(ops=root == config.ops_root)
        else:
            protect_directory(root)
            (root / MARKER).write_text(json.dumps({'environment': config.environment, 'database': config.database,
                                                'kind': 'ops' if root == config.ops_root else 'media'}), encoding='utf-8')
    lock = safe_path(config.check(ops=True), 'telemetry.lock')
    if not lock.exists():
        with lock.open('xb') as stream:
            stream.write(b'0')


def image_thumbnail(original: Path, thumbnail: Path, config: MediaConfig) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(original) as image:
                fmt = image.format
                if fmt not in ('JPEG', 'PNG', 'WEBP') or getattr(image, 'is_animated', False):
                    raise MediaError('仅支持静态JPEG、PNG和WebP图片')
                width, height = image.size
                if width * height > config.max_pixels or max(width, height) > config.max_edge:
                    raise MediaError('图片像素或最长边超过限制')
                image.verify()
            with Image.open(original) as image:
                image.load()
                preview = ImageOps.exif_transpose(image).convert('RGBA' if 'A' in image.getbands() else 'RGB')
                preview.thumbnail((960, 960))
                preview.info.clear()
                preview.save(thumbnail, format='WEBP', quality=85, exif=b'')
        return {'mime_type': {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}[fmt],
                'width': width, 'height': height}
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MediaError('图片损坏、类型无效或解码超限') from None


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description='显式初始化SelfLore私有媒体目录（不访问数据库）')
    parser.add_argument('--initialize',action='store_true',required=True)
    parser.add_argument('--environment',choices=('dev','prod'),required=True)
    parser.add_argument('--media-root',type=Path,required=True)
    parser.add_argument('--ops-root',type=Path,required=True)
    args=parser.parse_args(argv)
    from app.local_start import LocalConfigurationError
    try:
        initialize(MediaConfig(args.media_root,args.ops_root,args.environment,'selflore_'+args.environment))
        print('私有媒体目录已显式初始化；请配置同一环境和路径，并核对服务写权限。')
        return 0
    except (MediaError,LocalConfigurationError) as error:
        print(f'媒体初始化未完成：{error}'); return 1
    except OSError:
        print('媒体初始化文件访问失败，请核对指定目录权限。'); return 1


if __name__=='__main__': raise SystemExit(main())
