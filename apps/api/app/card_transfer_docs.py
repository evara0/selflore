"""Regenerate the published schema and API-shipped transfer documentation."""
import json
from pathlib import Path
from app.schemas.card_transfer import TransferDocument


def main():
    root = Path(__file__).resolve().parents[3]
    docs = root / 'docs/card-transfer'
    shipped = Path(__file__).resolve().parent / 'transfer_docs'
    example = json.loads((docs / 'example.json').read_text(encoding='utf-8-sig'))
    TransferDocument.model_validate(example)
    schema = TransferDocument.model_json_schema()
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    (docs / 'v1.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for source, target in [('README.md','guide.md'),('example.json','example.json'),('v1.schema.json','v1.schema.json')]:
        (shipped / target).write_bytes((docs / source).read_bytes())
    print('交换Schema、示例和API文档已同步；请运行test_card_package.py验证契约。')


if __name__ == '__main__':
    main()
