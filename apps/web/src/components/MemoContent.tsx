import { useEffect, useState, type CSSProperties } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import {
  useApi,
  useIdentity,
  useRefresh,
  cardUrl,
  type Card,
  type MemoItem,
  type MemoTarget,
} from '../lib/workspace'
import { Markdown } from './Common'

export function MemoExtraFields({
  item,
  columns,
  count = 1,
}: {
  item: MemoItem
  columns?: string[]
  count?: number
}) {
  return (
    <dl className="memo-extra-fields">
      {(item.extra_values || []).slice(0, count - 1).map((value, index) => (
        <div key={index}>
          <dt>{columns?.[index + 1] || `字段 ${index + 2}`}</dt>
          <dd>{value || '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function TargetLinks({ targets }: { targets?: MemoTarget[] }) {
  return (
    <div className="memo-targets">
      {targets?.map((t) =>
        t.lifecycle === 'active' ? (
          <Link key={t.id} to={cardUrl(t)}>
            {t.title} ↗
          </Link>
        ) : (
          <span key={t.id}>{t.title} · 暂不可用</span>
        ),
      )}
    </div>
  )
}
export default function MemoContent({
  card,
  readOnly = false,
}: {
  card: Card
  readOnly?: boolean
}) {
  const api = useApi(),
    refresh = useRefresh(),
    { guest, openLogin } = useIdentity()
  const [pending, setPending] = useState(false),
    [message, setMessage] = useState('')
  const [query] = useSearchParams(),
    location = useLocation()
  const requested = location.pathname.startsWith('/memos/') ? query.get('item') : null
  const items = card.memo_items || [],
    completed = items.filter((i) => i.is_completed).length
  useEffect(() => {
    if (requested)
      document.getElementById(`memo-item-${requested}`)?.scrollIntoView?.({ block: 'center' })
  }, [requested, card.id])
  async function complete(item: MemoItem) {
    if (guest) {
      openLogin()
      return
    }
    setPending(true)
    setMessage('')
    try {
      await api(`/cards/${card.id}/memo-items/${item.id}`, 'PATCH', {
        expected_revision: card.revision,
        is_completed: !item.is_completed,
      })
      await refresh()
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setPending(false)
    }
  }
  return (
    <>
      <Markdown text={card.body_md} />
      {card.memo_format === 'checklist' && (
        <>
          <p className="muted" aria-label="清单进度">
            已完成 {completed} / {items.length} 项
          </p>
          {requested && !items.some((i) => i.id === requested) && (
            <p role="status">该条目已不可用，仍可查看所属清单。</p>
          )}
          <ul
            className="memo-items tabular-read"
            aria-label="清单条目"
            style={{ '--memo-columns': card.memo_column_count || 1 } as CSSProperties}
          >
            <li className="checklist-table-heading" aria-hidden="true">
              <span title="完成状态">✓</span>
              {(card.memo_columns || ['条目'])
                .slice(0, card.memo_column_count || 1)
                .map((name, index) => (
                  <span key={index}>{name}</span>
                ))}
            </li>
            {items.map((item) => (
              <li
                id={`memo-item-${item.id}`}
                key={item.id}
                className={requested === item.id ? 'memo-item-highlight' : ''}
              >
                <div className="checklist-read-fields">
                  <label className="checklist-read-main">
                    <input
                      type="checkbox"
                      aria-label={item.text}
                      checked={item.is_completed}
                      disabled={readOnly || pending || card.lifecycle !== 'active'}
                      onChange={() => void complete(item)}
                    />
                    <span>
                      <small className="mobile-field-name">
                        {card.memo_columns?.[0] || '条目'}
                      </small>
                      <span className={item.is_completed ? 'completed-text' : ''}>{item.text}</span>
                    </span>
                  </label>
                  <MemoExtraFields
                    item={item}
                    columns={card.memo_columns}
                    count={card.memo_column_count}
                  />
                </div>
                <TargetLinks targets={item.targets} />
              </li>
            ))}
          </ul>
        </>
      )}
      {message && (
        <p role="alert">
          {message} <button onClick={() => void refresh()}>重新读取</button>
        </p>
      )}
    </>
  )
}
