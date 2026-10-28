import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from app.auth import current_user, get_db, get_settings
from app.main import create_app
from app.schemas.workspace import CardCreate
from app.services.card_import import MAX_IMPORT_BYTES, preview


CASES = [
    {'kind': 'knowledge', 'form': 'qa', 'question_md': '问题', 'answer_md': '答案'},
    {'kind': 'knowledge', 'form': 'cloze', 'body_md': '阅读 {{c1::论文}}'},
    {'kind': 'opinion', 'body_md': '自己的观点'},
    {'kind': 'reference', 'body_md': '摘录', 'note_md': '我的说明'},
    {'kind': 'memo', 'memo_format': 'note', 'body_md': '随手记'},
    {'kind': 'memo', 'memo_format': 'checklist', 'memo_items': [{'text': '阅读'}]},
]


@pytest.mark.parametrize('fields', CASES)
def test_all_card_types_use_existing_create_schema(fields):
    content = preview(json.dumps({'title': '导入示例', **fields}))
    card = CardCreate(**content, client_request_id=uuid4())
    assert card.kind == fields['kind']
    assert card.taxonomy_mode == 'unified'
    assert card.title == '导入示例'


def test_complete_user_checklist_example_preserves_all_columns_and_notes():
    sample = Path(__file__).parents[2] / 'web/public/examples/paper-reading-checklist.json'
    content = preview(sample.read_text(encoding='utf-8'))
    assert content['memo_column_count'] == 3
    assert content['memo_columns'] == ['项目', '根据对话确定的需求', '优先级／状态']
    assert len(content['memo_items']) == 11
    assert len({UUID(row['id']) for row in content['memo_items']}) == 11
    assert not any(row['is_completed'] for row in content['memo_items'])
    assert content['memo_items'][0]['extra_values'] == ['手机直接阅读，操作体验接近微信读书', '必须']
    assert content['memo_items'][-1]['text'] == '开放性'
    assert '系统通知' in content['body_md'] and '第一轮应先验收' in content['body_md']
    original_id = str(uuid4())
    content['memo_items'][0]['id'] = original_id
    again = preview(json.dumps(content))
    assert again == content


@pytest.mark.parametrize('text,part', [
    ('{', 'JSON 格式错误'),
    ('[]', '对象'), ('null', '对象'), ('"text"', '对象'),
    ('{"kind":"memo","kind":"opinion"}', '字段重复'),
    ('{"x":NaN}', 'JSON 不支持'), ('{"x":Infinity}', 'JSON 不支持'),
    ('{"title":"\\ud800","kind":"memo","memo_format":"note"}', 'Unicode'),
    ('{}', 'kind'),
    ('{"title":"X","kind":"unknown"}', 'kind'),
    ('{"title":"X","kind":"knowledge","form":"qa"}', '问答'),
    ('{"title":"X","kind":"memo","memo_format":"checklist"}', '清单至少一项'),
    ('{"title":"X","kind":"memo","memo_format":"note","owner_id":"x"}', 'owner_id'),
    ('{"title":"X","kind":"memo","memo_format":"note","client_request_id":"x"}', 'client_request_id'),
    ('{"title":"X","kind":"reference"}', '原始摘录'),
    ('{"title":"X","kind":"memo","memo_format":"checklist","memo_items":[{"text":" "}]}', 'memo_items.0.text'),
    ('{"title":"X","kind":"memo","memo_format":"checklist","memo_items":[null]}', 'memo_items.0'),
    ('{"title":"X","kind":"memo","memo_format":"checklist","memo_items":[{"text":"x","extra_values":["one"]}]}', 'extra_values'),
])
def test_invalid_imports_report_specific_field_or_format(text, part):
    with pytest.raises(HTTPException) as error:
        preview(text)
    assert error.value.status_code == 422
    assert part in error.value.detail['message']


def test_utf8_size_bom_and_repeated_row_ids():
    note = {'title': '备忘', 'kind': 'memo', 'memo_format': 'note'}
    assert preview('\ufeff' + json.dumps(note))['title'] == '备忘'
    with pytest.raises(HTTPException, match='1 MiB'):
        preview('中' * (MAX_IMPORT_BYTES // 3 + 1))
    for fields in [
        {'memo_columns': ['一列']}, {'memo_column_count': 4},
        {'memo_items': [{'id': str(UUID(int=1)), 'text': 'x'}] * 2},
        {'memo_items': [{'text': str(i)} for i in range(201)]},
    ]:
        with pytest.raises(HTTPException):
            preview(json.dumps({**note, 'memo_format': 'checklist', 'memo_items': [{'text': 'x'}], **fields}))


def test_preview_route_auth_csrf_no_business_db_and_create_contract(monkeypatch):
    app = create_app(Path('/nonexistent-dist'))
    db_calls, writes = [], []
    def fake_db():
        db_calls.append(True)
        return None
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(origins=('http://testserver',), cookie_name='session')
    client = TestClient(app)
    body = {'json_text': json.dumps({'kind': 'memo', 'memo_format': 'checklist', 'title': '清单', 'memo_items': [{'text': '阅读'}]})}
    headers = {'Origin': 'http://testserver', 'X-CSRF-Token': 'csrf'}
    assert client.post('/api/cards/import-preview', json=body, headers=headers).status_code == 401
    app.dependency_overrides[current_user] = lambda: ('owner', 'test', 'member', True, 'csrf')
    assert client.post('/api/cards/import-preview', json=body).status_code == 403
    assert client.post('/api/cards/import-preview', json=body, headers={'Origin': 'http://wrong'}).status_code == 403
    assert client.post('/api/cards/import-preview', json=body, headers={'Origin': 'http://testserver'}).status_code == 403
    def create(db, owner, content):
        writes.append((owner, content))
        return {'id': str(uuid4()), 'kind': content.kind}
    monkeypatch.setattr('app.routers.workspace.cards.create_card', create)
    db_calls.clear()
    response = client.post('/api/cards/import-preview', json=body, headers=headers)
    assert response.status_code == 200
    assert not writes and not db_calls
    content = response.json()
    assert content['memo_items'][0]['id']
    result = client.post('/api/cards', json={**content, 'client_request_id': str(uuid4())}, headers=headers)
    assert result.status_code == 201
    assert len(writes) == 1 and writes[0][0] == 'owner'
    assert str(writes[0][1].memo_items[0].id) == content['memo_items'][0]['id']
