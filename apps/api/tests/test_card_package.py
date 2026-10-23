import io
import json
from pathlib import Path
import zipfile
import pytest
from fastapi import HTTPException
from app.services.card_package import Package, rewrite
from app.schemas.card_transfer import TransferDocument

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / 'docs/card-transfer/example.json'


def test_schema_and_shipped_documents():
    schema = TransferDocument.model_json_schema()
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(EXAMPLE.read_bytes()))
    assert schema == json.loads((EXAMPLE.parent / 'v1.schema.json').read_bytes())
    for public, shipped in [('README.md','guide.md'),('example.json','example.json'),('v1.schema.json','v1.schema.json')]:
        assert (EXAMPLE.parent/public).read_bytes() == (ROOT/'apps/api/app/transfer_docs'/shipped).read_bytes()
    package = Package(io.BytesIO(EXAMPLE.read_bytes()))
    try:
        assert package.summary()['card_count'] == 6
        assert package.summary()['asset_count'] == 0
    finally:
        package.close()


@pytest.mark.parametrize('raw', [b'{"version":1,"version":1}', b'{"x":NaN}', b'not json'])
def test_strict_json(raw):
    with pytest.raises(HTTPException) as error:
        Package(io.BytesIO(raw))
    assert error.value.status_code == 422


@pytest.mark.parametrize('mutate', [
    lambda d: d.update(version=2),
    lambda d: d.update(version=True),
    lambda d: d['cards'][0].update(is_bookmarked="false"),
    lambda d: d['cards'][0].update(owner_id='someone'),
    lambda d: d['cards'][0].update(answer_md=''),
    lambda d: d['cards'][1].update(key='qa'),
    lambda d: d['cards'][0].update(link_keys=['missing']),
    lambda d: d['cards'][0].update(link_keys=['qa']),
    lambda d: d['cards'][0].update(answer_md='[[card:missing|缺失]]'),
    lambda d: d['cards'][0].update(answer_md='[[00000000-0000-0000-0000-000000000001]]'),
    lambda d: d['cards'][0].update(tags=['Ａ','A']),
])
def test_contract_rejections(mutate):
    raw = json.loads(EXAMPLE.read_bytes()); mutate(raw)
    with pytest.raises(HTTPException) as error:
        Package(io.BytesIO(json.dumps(raw).encode()))
    assert error.value.detail['errors'][0]['path']


def test_reference_code_preserved():
    text = '正文 [[card:a|标题]] `[[card:a]]`\n```\n[[card:a]]\n```'
    translated = rewrite(text, {'a':'uuid'}, importing=True)
    assert translated == '正文 [[uuid|标题]] `[[card:a]]`\n```\n[[card:a]]\n```'


@pytest.mark.parametrize('name', ['../escape', '/root.png', 'media/a.png', 'media/../a.png'])
def test_unexpected_zip_members(name):
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('manifest.json', EXAMPLE.read_bytes())
        archive.writestr(name,b'bad')
    with pytest.raises(HTTPException):
        Package(io.BytesIO(output.getvalue()))


def test_post_mapping_size_limit(monkeypatch):
    raw = json.loads(EXAMPLE.read_bytes())
    raw['cards'][0]['answer_md'] = 'x' * (65536 - len('[[card:opinion]]')) + '[[card:opinion]]'
    with pytest.raises(HTTPException) as error:
        Package(io.BytesIO(json.dumps(raw).encode()))
    assert '64 KiB' in error.value.detail['message']


def test_declared_budgets(monkeypatch):
    import app.services.card_package as packages
    monkeypatch.setattr(packages, 'MAX_JSON', 10)
    with pytest.raises(HTTPException):
        Package(io.BytesIO(EXAMPLE.read_bytes()))
    monkeypatch.setattr(packages, 'MAX_ARCHIVE', 10)
    with pytest.raises(HTTPException):
        Package(io.BytesIO(EXAMPLE.read_bytes()))
