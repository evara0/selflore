from __future__ import annotations

from psycopg.rows import dict_row
from fastapi import HTTPException


def one(db, query, values=()):
    with db.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, values)
        return cursor.fetchone()


def many(db, query, values=()):
    with db.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, values)
        return cursor.fetchall()


def run(db, query, values=()):
    with db.cursor() as cursor:
        cursor.execute(query, values)


def fail(status, code, message, **extra):
    raise HTTPException(status, {'code': code, 'message': message, **extra})


def owned(db, table, owner, entity, *, lock=False):
    if table not in {'cards','collections'}:
        raise ValueError('invalid entity table')
    row = one(db, f'SELECT * FROM app.{table} WHERE owner_id=%s AND id=%s' + (' FOR UPDATE' if lock else ''), (owner,entity))
    if row is None:
        fail(404,'not_found','对象不存在或不可用')
    return row


def revision(row, expected):
    if row['revision'] != expected:
        fail(409,'revision_conflict','内容已在其他位置更新，请重新加载后合并',current_revision=row['revision'])
