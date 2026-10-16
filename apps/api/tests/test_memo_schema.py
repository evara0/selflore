from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.workspace import CardCreate, CardPatch


def test_memo_schema_boundaries_and_server_fields():
    base={'kind':'memo','memo_format':'note','title':'备忘','client_request_id':uuid4()}
    assert CardCreate(**base).body_md is None
    one={'id':uuid4(),'text':'阅读'}
    assert len(CardCreate(**{**base,'memo_format':'checklist','memo_items':[dict(one,id=uuid4()) for _ in range(200)]}).memo_items)==200
    invalid=[{'title':' '},{'title':'a'*201},{'form':'qa'},{'memo_format':None},{'memo_format':'checklist'},
             {'body_md':'a'*65537},{'topic_ids':[uuid4()]},{'tag_ids':[str(uuid4())]*2},
             {'memo_items':[one]},{'note_md':'个人说明'},{'question_md':'问题'},{'owner_id':str(uuid4())},
             {'memo_format':'checklist','memo_items':[dict(one,text=' ')]},
             {'memo_format':'checklist','memo_items':[dict(one,text='a'*2001)]},
             {'memo_format':'checklist','memo_items':[dict(one,id=uuid4()) for _ in range(201)]},
             {'memo_format':'checklist','memo_items':[one,one]},
             {'memo_format':'checklist','memo_items':[dict(one,completed_at='2026-01-01T00:00:00Z')]},
             {'memo_format':'checklist','memo_items':[dict(one,target_ids=[uuid4() for _ in range(21)])]}]
    for values in invalid:
        with pytest.raises(ValidationError): CardCreate(**{**base,**values})
    with pytest.raises(ValidationError): CardPatch(expected_revision=1,memo_format='checklist')
