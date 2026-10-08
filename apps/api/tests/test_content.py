from datetime import datetime,timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.workspace import CardContent,ProfilePatch
from app.services.content import cloze_indices,cloze_text,references
from app.services.scheduling import fresh,schedule


def test_cloze_units_and_code_blocks():
    text='{{c1::主动回忆::方法}}和{{c1::提取}}，{{c2::间隔}}。\n```\n{{c3::示例}}\n```'
    assert cloze_indices(text)==[1,2]
    assert '【方法】和【…】，间隔' in cloze_text(text,1,False)
    assert '{{c3::示例}}' in cloze_text(text,1,True)
    assert '主动回忆和提取' in cloze_text(text,None,True)


@pytest.mark.parametrize('text',['没有填空','{{c1::::提示}}','{{c0::答案}}','{{c100::答案}}','{{c1::{{c2::嵌套}}}}'])
def test_invalid_cloze_rejected(text):
    with pytest.raises(ValueError): cloze_indices(text)


def test_stable_references_ignore_code_and_unresolved_titles():
    first,second=uuid4(),uuid4()
    assert references(f'[[{first}|主动回忆]] [[同名标题]] `[[{second}|代码]]`')=={first}
    with pytest.raises(ValueError): references('[[not-a-uuid|错误]]')


def test_content_shape_byte_limit_and_profile_timezone():
    with pytest.raises(ValidationError): CardContent(kind='knowledge',form='qa',title='问题',question_md='问题',answer_md='')
    with pytest.raises(ValidationError): CardContent(kind='opinion',title='观点',body_md='中'*22000)
    with pytest.raises(ValidationError): ProfilePatch(expected_revision=1,timezone='Unknown/Zone')
    assert ProfilePatch(expected_revision=1,timezone='Asia/Shanghai').timezone=='Asia/Shanghai'


def test_fsrs_fixed_clock_roundtrip_four_ratings():
    now=datetime(2026,10,4,tzinfo=timezone.utc); payload=fresh(now)
    result=[schedule(payload,rating,now) for rating in range(1,5)]
    assert result[0][2]<result[3][2]
    assert schedule(payload,3,now)==schedule(payload,3,now)
    assert all(state in {'learning','review','relearning'} for _,state,_ in result)
    serialized,state,due=result[2]
    assert schedule(serialized,3,due)[2]>due
