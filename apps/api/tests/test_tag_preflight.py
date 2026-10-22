from uuid import UUID
import pytest
from app.tag_preflight import inspect
from app.services.tags import normalize_name


def test_normalization_limits_and_case():
    assert normalize_name('\u3000ＡＩ\u0085')=='AI'
    assert normalize_name('a  b')=='a  b'
    assert normalize_name('Ai')!='AI'
    assert normalize_name('字'*80)=='字'*80
    for value in (' \t','字'*81):
        with pytest.raises(ValueError): normalize_name(value)


def test_owner_local_deterministic_winner_and_relationship_union():
    rows=[{'owner_id':owner,'id':UUID(int=n),'source_type':source,'name':name,'created_at':'2026-01-01'}
        for owner,n,source,name in [('a',1,'topic','ＡＩ'),('a',2,'tag','AI'),('a',3,'topic','AI'),('b',4,'topic','AI')]]
    relations=[{'owner_id':r['owner_id'],'card_id':'c','source_type':r['source_type'],'source_id':r['id']} for r in rows]
    result=inspect(rows,relations)
    assert result['groups'][0]['preferred_id']==str(UUID(int=2))
    assert result['owners']['a']==dict(source_labels=3,canonical_labels=1,source_relations=3,canonical_relations=1,merged_groups=1)
    assert result['owners']['b']['canonical_labels']==1
    assert inspect(list(reversed(rows)),relations)['groups']==result['groups']
    with pytest.raises(ValueError): inspect(rows,[{**relations[0],'owner_id':'other'}])


def test_30_relationship_limit():
    rows=[dict(owner_id='a',id=UUID(int=n+1),source_type='tag',name=str(n),created_at='2026') for n in range(31)]
    relations=[dict(owner_id='a',card_id='c',source_type='tag',source_id=r['id']) for r in rows]
    assert inspect(rows[:30],relations[:30])['owners']['a']['canonical_relations']==30
    with pytest.raises(ValueError): inspect(rows,relations)
