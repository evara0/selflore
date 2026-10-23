"""Bounded, private portable packages and semantic validation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import stat
from tempfile import TemporaryDirectory
import zipfile
from uuid import UUID
from pydantic import ValidationError
from app.schemas.card_transfer import TransferDocument, MAX_JSON, MAX_ARCHIVE, MAX_MEMBERS, EXCLUDED
from app.services.content import REFERENCE, prose
from app.media_storage import MediaConfig, MediaError, image_thumbnail, file_hash
from app.repositories.workspace import fail

TEXT_FIELDS = ('question_md', 'answer_md', 'body_md', 'note_md')


def issue(path, message, card_key=None, code='invalid_transfer'):
    fail(422, code, message, errors=[dict(path=path, message=message, card_key=card_key, code=code)])


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON对象键重复：' + key)
        result[key] = value
    return result


def parse_json(raw):
    if len(raw) > MAX_JSON:
        issue('$', 'JSON超过32 MiB限制')
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=object_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('非法数值')))
    except (ValueError, UnicodeError, RecursionError):
        issue('$', 'JSON无效、对象键重复或嵌套过深')


def rewrite(text, mapping, *, importing):
    if not text:
        return text
    clean = prose(text)
    for match in reversed(list(REFERENCE.finditer(clean))):
        token = match[1]
        if importing:
            if token.startswith('card:'):
                key = token[5:]
                if key not in mapping:
                    raise ValueError('引用目标不存在：' + key)
                target = str(mapping[key])
            else:
                try:
                    UUID(token)
                except ValueError:
                    if match[2] is not None:
                        raise ValueError('内部引用请使用card:key') from None
                    continue
                raise ValueError('不能使用原数据库UUID引用')
        else:
            try:
                key = str(UUID(token))
            except ValueError:
                continue
            if key not in mapping:
                raise ValueError('引用目标不在导出范围')
            target = 'card:' + mapping[key]
        suffix = '|' + match[2] if match[2] is not None else ''
        text = text[:match.start()] + '[[' + target + suffix + ']]' + text[match.end():]
    return text


class Package:
    def __init__(self, stream, config=None):
        self.temp = TemporaryDirectory(prefix='selflore-transfer-')
        self.root = Path(self.temp.name)
        self.images = {}
        self.config = config or MediaConfig.load()
        try:
            self.load(stream)
        except BaseException:
            self.close()
            raise

    def close(self):
        self.temp.cleanup()

    def load(self, stream):
        source = self.root / 'input'
        total = 0
        with source.open('wb') as output:
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_ARCHIVE:
                    issue('$', '输入超过512 MiB限制')
                output.write(chunk)
        if zipfile.is_zipfile(source):
            try:
                with zipfile.ZipFile(source) as archive:
                    members = archive.infolist()
                    names = [i.filename for i in members]
                    if len(members) > MAX_MEMBERS or len(names) != len(set(names)) or 'manifest.json' not in names:
                        issue('$', 'ZIP成员过多、重复或缺少manifest.json')
                    if sum(i.file_size for i in members) > MAX_ARCHIVE:
                        issue('$', '解压总量超过512 MiB')
                    for member in members:
                        name = member.filename
                        if (name != 'manifest.json' and not re.fullmatch(r'media/[A-Za-z0-9_-]{1,80}\.(png|jpg|webp)', name)) or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                            issue('$', 'ZIP路径、类型或加密成员不受支持')
                    info = archive.getinfo('manifest.json')
                    if info.file_size > MAX_JSON:
                        issue('$', 'JSON超过32 MiB限制')
                    self.document = self.validate(parse_json(archive.read(info)))
                    expected = {'manifest.json', *[a.path for a in self.document.assets]}
                    if set(names) != expected:
                        issue('assets', 'ZIP存在缺失或未声明成员')
                    budget = info.file_size
                    for asset in self.document.assets:
                        local_key = hashlib.sha256(asset.key.encode()).hexdigest()
                        original = self.root / (local_key + '.bin')
                        thumb = self.root / (local_key + '.webp')
                        size = 0
                        digest = hashlib.sha256()
                        with archive.open(asset.path) as incoming, original.open('wb') as output:
                            while chunk := incoming.read(1024 * 1024):
                                size += len(chunk)
                                budget += len(chunk)
                                if size > min(self.config.max_bytes, asset.bytes) or budget > MAX_ARCHIVE:
                                    issue('assets.' + asset.key, '原图或解压总量超限')
                                digest.update(chunk)
                                output.write(chunk)
                        if size != asset.bytes or digest.hexdigest() != asset.sha256:
                            issue('assets.' + asset.key, '图片字节数或摘要不符')
                        meta = image_thumbnail(original, thumb, self.config)
                        if meta['mime_type'] != asset.mime_type:
                            issue('assets.' + asset.key, '图片类型不符')
                        self.images[asset.key] = (original, thumb, meta)
            except (zipfile.BadZipFile, RuntimeError, EOFError):
                issue('$', 'ZIP损坏或无法解压')
        else:
            if source.stat().st_size > MAX_JSON:
                issue('$', 'JSON超过32 MiB限制')
            self.document = self.validate(parse_json(source.read_bytes()))
            if self.document.assets:
                issue('assets', '含图片内容请使用ZIP包')
        self.digest = hashlib.sha256(self.document.model_dump_json().encode()).hexdigest()

    def validate(self, raw):
        try:
            document = TransferDocument.model_validate(raw)
        except ValidationError as error:
            errors = []
            for item in error.errors(include_url=False, include_context=False, include_input=False):
                loc = item['loc']
                key = None
                if len(loc) > 1 and loc[0] == 'cards' and isinstance(raw, dict):
                    entries = raw.get('cards')
                    if isinstance(entries, list) and isinstance(loc[1], int) and loc[1] < len(entries) and isinstance(entries[loc[1]], dict):
                        key = entries[loc[1]].get('key')
                errors.append(dict(path='.'.join(map(str, loc)), message=item['msg'], code=item['type'], card_key=key))
            fail(422, 'invalid_transfer', '交换格式校验失败', errors=errors)
        keys = [c.key for c in document.cards]
        asset_keys = [a.key for a in document.assets]
        if len(keys) != len(set(keys)):
            issue('cards', '卡片key重复')
        if len(asset_keys) != len(set(asset_keys)) or len({a.path for a in document.assets}) != len(document.assets):
            issue('assets', '附件key或路径重复')
        mapping = {key: '00000000-0000-0000-0000-000000000001' for key in keys}
        used = set()
        for card in document.cards:
            for field in TEXT_FIELDS:
                try:
                    translated = rewrite(getattr(card, field), mapping, importing=True)
                    if translated and len(translated.encode('utf-8')) > 65536:
                        raise ValueError('引用转换后的正文超过64 KiB')
                except ValueError as error:
                    issue('cards.' + card.key + '.' + field, str(error), card.key)
                targets = [m[1][5:] for m in REFERENCE.finditer(prose(getattr(card, field) or '')) if m[1].startswith('card:')]
                if card.key in targets:
                    issue('cards.' + card.key + '.' + field, '不能引用自身', card.key)
            for target in [*card.link_keys, *[key for i in card.memo_items for key in i.target_keys]]:
                if target not in mapping or target == card.key:
                    issue('cards.' + card.key, '关系目标不存在或指向自身', card.key)
            for a in card.attachments:
                if a.asset_key not in asset_keys:
                    issue('cards.' + card.key + '.attachments', '附件目标不存在', card.key)
                used.add(a.asset_key)
        if used != set(asset_keys):
            issue('assets', '附件必须被卡片引用')
        if document.export_info and document.export_info.card_count != len(document.cards):
            issue('export_info.card_count', '导出卡片数量不符')
        return document

    def summary(self):
        return dict(digest=self.digest, card_count=len(self.document.cards), asset_count=len(self.document.assets),
                    counts={kind: sum(c.kind == kind for c in self.document.cards) for kind in ('knowledge','opinion','reference','memo')},
                    excluded=EXCLUDED, errors=[])
