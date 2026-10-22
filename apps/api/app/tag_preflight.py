"""Read-only legacy taxonomy inventory; never migrates or writes the target."""
import argparse
import json
import hashlib
from collections import defaultdict
import psycopg
from psycopg.rows import dict_row
from app.services.tags import normalize_name


def inspect(rows, relations):
    groups=defaultdict(list)
    by_source={}
    for row in rows:
        key=(str(row['owner_id']),normalize_name(row['name']))
        groups[key].append(row)
        by_source[(str(row['owner_id']),row['source_type'],str(row['id']))]=key
    cards=defaultdict(set)
    for relation in relations:
        source=(str(relation['owner_id']),relation['source_type'],str(relation['source_id']))
        if source not in by_source: raise ValueError('旧关系缺少同账号标签')
        cards[(str(relation['owner_id']),str(relation['card_id']))].add(by_source[source])
    if any(len(keys)>30 for keys in cards.values()): raise ValueError('旧卡片合并后超过30标签')
    owners=defaultdict(lambda: {'source_labels':0,'canonical_labels':0,'source_relations':0,'canonical_relations':0,'merged_groups':0})
    winners=[]
    for (owner,name),members in sorted(groups.items()):
        winner=sorted(members,key=lambda r:(r['source_type']!='tag',str(r['created_at']),str(r['id'])))[0]
        winners.append({'owner_id':owner,'name':name,'preferred_id':str(winner['id']),'sources':len(members)})
        owners[owner]['source_labels']+=len(members); owners[owner]['canonical_labels']+=1
        owners[owner]['merged_groups']+=int(len(members)>1)
    for r in relations: owners[str(r['owner_id'])]['source_relations']+=1
    for (owner,_),keys in cards.items(): owners[owner]['canonical_relations']+=len(keys)
    fingerprint=hashlib.sha256(json.dumps({'labels':rows,'relations':relations},default=str,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'fingerprint':fingerprint,'owners':dict(owners),'groups':winners,'orphans':0}


def report(db):
    rows=db.execute("""SELECT owner_id,id,'tag' AS source_type,NULL::text AS kind,name,created_at FROM app.tags
        UNION ALL SELECT owner_id,id,'topic',kind,name,created_at FROM app.topics ORDER BY owner_id,source_type,id""").fetchall()
    relations=db.execute("""SELECT r.owner_id,r.card_id,'tag' AS source_type,r.tag_id AS source_id,c.kind,c.lifecycle
        FROM app.card_tags r JOIN app.cards c ON c.owner_id=r.owner_id AND c.id=r.card_id
        UNION ALL SELECT r.owner_id,r.card_id,'topic',r.topic_id,c.kind,c.lifecycle
        FROM app.card_topics r JOIN app.cards c ON c.owner_id=r.owner_id AND c.id=r.card_id ORDER BY owner_id,card_id,source_type,source_id""").fetchall()
    result=inspect(rows,relations)
    result['content_counts']=[dict(r) for r in db.execute('SELECT owner_id,kind,lifecycle,count(*) FROM app.cards GROUP BY owner_id,kind,lifecycle ORDER BY 1,2,3').fetchall()]
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn',required=True,help='Explicit target; omit passwords and use a private pgpass file')
    args=parser.parse_args()
    with psycopg.connect(args.dsn,row_factory=dict_row) as db:
        db.execute('SET TRANSACTION READ ONLY ISOLATION LEVEL REPEATABLE READ')
        print(json.dumps(report(db),ensure_ascii=False,default=str,indent=2))


if __name__=='__main__': main()
