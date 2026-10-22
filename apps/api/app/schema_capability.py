"""Readiness and rollback contracts; no schema mutations or history permissions."""
CAPABILITY='reference-memo-tags-v1'


def ready(connection):
    try:
        connection.execute('SELECT normalized_name FROM app.tags LIMIT 0')
        for table in ('tag_aliases','card_tag_sources','memo_items','memo_item_links'):
            connection.execute(f'SELECT 1 FROM app.{table} LIMIT 0')
        return True
    except Exception:
        return False


def compatible(previous, current=CAPABILITY):
    return previous==current==CAPABILITY
