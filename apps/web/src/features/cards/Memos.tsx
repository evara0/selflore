import { TagFilter } from '../../components/Selectors'
import { tagQuery } from '../../lib/tag-filter'
import { useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import {
  useApi,
  useData,
  useIdentity,
  useRefresh,
  cardUrl,
  params,
  type Card,
  type MemoItem,
  type Page,
} from '../../lib/workspace'
import { PageHeading, Pager, QueryState, Tags } from '../../components/Common'
import { TargetLinks } from '../../components/MemoContent'

type OpenItem = MemoItem & { memo_card_id: string; memo_title: string; revision: number }
export default function Memos() {
  const location = useLocation()
  const [search, setSearch] = useSearchParams(),
    view = search.get('view') || 'all',
    q = search.get('q') || '',
    offset = Number(search.get('offset') || 0)
  const open = view === 'open',
    api = useApi(),
    refresh = useRefresh(),
    { guest, openLogin } = useIdentity()
  const [message, setMessage] = useState(''),
    [pending, setPending] = useState<string | null>(null)
  const memoParams = params({
    kind: 'memo',
    memo_format: view === 'note' || view === 'checklist' ? view : undefined,
    lifecycle: search.get('lifecycle') || 'active',
    q,
    limit: 12,
    offset,
  })
  const cards = useData<Page<Card>>(`/cards?${memoParams}&${tagQuery(search)}`, !open)
  const tasks = useData<Page<OpenItem>>(
    `/memo-items?${params({ is_completed: false, q, limit: 12, offset })}&${tagQuery(search)}`,
    open,
  )
  const data = open ? tasks.data : cards.data
  function update(key: string, value: string) {
    const next = new URLSearchParams(search)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'offset') next.delete('offset')
    setSearch(next)
  }
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(search)
      next.set('offset', String(Math.max(0, Math.ceil(data.total / data.limit) - 1) * data.limit))
      setSearch(next, { replace: true })
    }
  }, [data, offset, search, setSearch])
  async function complete(item: OpenItem) {
    if (guest) {
      openLogin()
      return
    }
    setPending(item.id)
    setMessage('')
    try {
      await api(`/cards/${item.memo_card_id}/memo-items/${item.id}`, 'PATCH', {
        expected_revision: item.revision,
        is_completed: true,
      })
      await refresh()
    } catch (e) {
      setMessage((e as Error).message)
    } finally {
      setPending(null)
    }
  }
  return (
    <>
      <PageHeading title="备忘">
        <Link className="button" to="/new?kind=memo&memo_format=note">
          ＋ 随手记
        </Link>
        <Link className="button primary" to="/new?kind=memo&memo_format=checklist">
          ＋ 新建清单
        </Link>
      </PageHeading>
      <section className="panel memo-workspace">
        <div className="filter-tabs">
          {[
            ['all', '全部'],
            ['note', '随手记'],
            ['checklist', '清单'],
            ['open', '未完成事项'],
          ].map(([value, label]) => (
            <button
              key={value}
              className={view === value ? 'selected' : ''}
              onClick={() => update('view', value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="toolbar">
          <input
            aria-label="搜索备忘"
            value={q}
            onChange={(e) => update('q', e.target.value)}
            placeholder="搜索标题、正文或条目…"
          />
          {!open && (
            <select
              aria-label="备忘状态"
              value={search.get('lifecycle') || 'active'}
              onChange={(e) => update('lifecycle', e.target.value)}
            >
              <option value="active">正常备忘</option>
              <option value="archived">已归档</option>
            </select>
          )}
        </div>
        <TagFilter />
        <p className="muted">
          {data?.total ?? '—'} {open ? '项未完成事项' : '张备忘卡'}
        </p>
        <p role="status">{message}</p>
        <QueryState query={open ? tasks : cards}>
          {open ? (
            <ul className="memo-items">
              {tasks.data?.items.map((item) => (
                <li key={item.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={false}
                      disabled={!!pending}
                      onChange={() => void complete(item)}
                    />
                    <span>{item.text}</span>
                  </label>
                  <Link
                    to={`/memos/${item.memo_card_id}?item=${item.id}`}
                    state={{ from: location.pathname + location.search }}
                  >
                    所属清单：{item.memo_title} ↗
                  </Link>
                  <TargetLinks targets={item.targets} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="card-grid">
              {cards.data?.items.map((card) => (
                <article className="memo-card panel print-card" key={card.id}>
                  <small>{card.memo_format === 'checklist' ? '清单' : '随手记'}</small>
                  <h2>
                    <Link to={cardUrl(card)} state={{ from: location.pathname + location.search }}>
                      {card.title}
                    </Link>
                  </h2>
                  <p>{card.excerpt}</p>
                  {card.memo_format === 'checklist' && (
                    <p>
                      已完成 {card.memo_progress?.completed ?? 0} / {card.memo_progress?.total ?? 0}{' '}
                      项
                    </p>
                  )}
                  <Tags items={card.tags} />
                </article>
              ))}
            </div>
          )}
          {data?.total === 0 && (
            <p className="state">{open ? '没有未完成事项。' : '还没有备忘，先记下一件事。'}</p>
          )}
          {data && <Pager {...data} onChange={(n) => update('offset', String(n))} />}
        </QueryState>
      </section>
    </>
  )
}
