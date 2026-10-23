import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useApi,
  useData,
  useRefresh,
  params,
  cardKindName,
  type Card,
  type Page,
  type Label,
  ApiError,
} from '../lib/workspace'
import { QueryState } from './Common'

export function CardPicker({
  onSelect,
  excluded = [],
  kind,
  disabled = false,
}: {
  onSelect: (card: Card) => void
  excluded?: string[]
  kind?: string
  disabled?: boolean
}) {
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const query = useData<Page<Card>>(`/cards?${params({ q, kind, limit: 20, offset })}`)
  return (
    <div className="card-picker">
      <input
        aria-label="搜索要关联的卡片"
        placeholder="搜索标题、内容或编号…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setOffset(0)
        }}
      />
      <QueryState query={query}>
        <div className="picker-results">
          {query.data?.items
            .filter((c) => !excluded.includes(c.id) && (!kind || c.kind === kind))
            .map((c) => (
              <button type="button" key={c.id} disabled={disabled} onClick={() => onSelect(c)}>
                <b>{c.title}</b>
                <small>
                  {cardKindName(c.kind)} · {c.code}
                </small>
              </button>
            ))}
        </div>
        {query.data && offset + 20 < query.data.total && (
          <button type="button" onClick={() => setOffset(offset + 20)}>
            更多卡片
          </button>
        )}
      </QueryState>
    </div>
  )
}

export function TagSelector({
  selected,
  onChange,
  allowCreate = false,
}: {
  selected: string[]
  onChange: (ids: string[]) => void
  allowCreate?: boolean
}) {
  const query = useData<{ items: Label[] }>('/tags')
  const api = useApi(),
    refresh = useRefresh()
  const [name, setName] = useState(''),
    [message, setMessage] = useState(''),
    [pending, setPending] = useState(false),
    [closed, setClosed] = useState(false),
    [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const [created, setCreated] = useState<Label[]>([])
  const items = [
    ...(query.data?.items || []),
    ...created.filter((t) => !query.data?.items.some((i) => i.id === t.id)),
  ]
  const visible = items.filter((t) => t.name.toLocaleLowerCase().includes(name.toLocaleLowerCase()))
  const options = visible.filter((t) => !selected.includes(t.id))
  const highlighted = options[active % Math.max(1, options.length)]
  useEffect(() => {
    if (document.activeElement === input.current)
      input.current
        ?.closest('.tag-selector')
        ?.querySelector('.keyboard-active')
        ?.scrollIntoView?.({ block: 'nearest' })
  }, [active, selected.length])
  function toggle(id: string) {
    if (!selected.includes(id) && selected.length >= 30) {
      setMessage('最多选择30个标签')
      return
    }
    onChange(selected.includes(id) ? selected.filter((i) => i !== id) : [...selected, id])
    setMessage('')
  }
  async function create() {
    if (!name.trim() || pending || selected.length >= 30) return
    setPending(true)
    setMessage('')
    try {
      const label = await api<Label>('/tags', 'POST', { name })
      setCreated((old) => [...old, label])
      onChange([...new Set([...selected, label.id])])
      setName('')
      await refresh()
    } catch (error) {
      const existing = error instanceof ApiError ? error.existingTag : undefined
      if (existing) {
        setCreated((old) => [...old, existing])
        onChange([...new Set([...selected, existing.id])])
        setName('')
        setMessage('已选用同名标签')
      } else setMessage((error as Error).message)
    } finally {
      setPending(false)
      input.current?.focus()
    }
  }
  return (
    <div className="labels-editor tag-selector">
      <span className="field-label">标签 · {selected.length}/30</span>
      <div className="choice-tags" aria-label="已选标签">
        {selected.map((id) => (
          <button
            type="button"
            className="selected"
            key={id}
            aria-label={`移除 ${items.find((t) => t.id === id)?.name || '标签'}`}
            onClick={() => toggle(id)}
          >
            {items.find((t) => t.id === id)?.name ||
              (query.isPending ? '标签加载中' : '不可用标签')}{' '}
            ×
          </button>
        ))}
      </div>
      {!selected.length && <small className="muted">可稍后整理</small>}
      <div className="inline-form">
        <input
          ref={input}
          aria-label="搜索标签"
          placeholder={allowCreate ? '搜索或新建标签…' : '搜索标签…'}
          value={name}
          maxLength={160}
          onFocus={() => setClosed(false)}
          onChange={(e) => {
            setName(e.target.value)
            setClosed(false)
            setActive(0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault()
              setClosed(false)
              setActive(
                (active + (e.key === 'ArrowDown' ? 1 : -1) + options.length) %
                  Math.max(1, options.length),
              )
            }
            if (e.key === 'Escape') {
              e.preventDefault()
              setClosed(true)
              input.current?.focus()
            }
            if (e.key === 'Enter') {
              e.preventDefault()
              if (highlighted && !closed) toggle(highlighted.id)
              else if (allowCreate) void create()
            }
          }}
        />
        {allowCreate && (
          <button
            type="button"
            disabled={pending || !name.trim() || selected.length >= 30}
            onClick={() => void create()}
          >
            {pending ? '创建中…' : '新建标签'}
          </button>
        )}
      </div>
      {!closed && highlighted && (
        <small className="muted">Enter 选择：{highlighted.name}；方向键切换，Esc 收起</small>
      )}
      <QueryState query={query}>
        {!closed && (
          <div className="choice-tags tag-options" aria-label="可选标签">
            {visible
              .filter((t) => !selected.includes(t.id))
              .map((t) => (
                <button
                  type="button"
                  key={t.id}
                  className={highlighted?.id === t.id ? 'keyboard-active' : ''}
                  disabled={selected.length >= 30}
                  onClick={() => toggle(t.id)}
                >
                  {t.name}
                  {t.card_count !== undefined && <small> · {t.card_count}</small>}
                </button>
              ))}
            {!visible.length && (
              <small className="muted">没有匹配标签{allowCreate ? '，可以新建' : ''}</small>
            )}
          </div>
        )}
      </QueryState>
      <small className="muted">账号内共用，使用数包含备忘</small>
      {message && <p role="status">{message}</p>}
    </div>
  )
}

export function Labels({
  tags,
  onChange,
}: {
  kind: string
  topics: string[]
  tags: string[]
  onChange: (topics: string[], tags: string[]) => void
}) {
  return <TagSelector selected={tags} onChange={(ids) => onChange([], ids)} allowCreate />
}

export function TagFilter() {
  const [search, setSearch] = useSearchParams()
  const ids = search.getAll('tag_ids')
  function update(nextIds: string[], match = search.get('tag_match') || 'all') {
    const next = new URLSearchParams(search)
    for (const key of ['tag_ids', 'topic', 'tag', 'offset']) next.delete(key)
    nextIds.sort().forEach((id) => next.append('tag_ids', id))
    if (nextIds.length) next.set('tag_match', match)
    else next.delete('tag_match')
    setSearch(next)
  }
  return (
    <details
      className="tag-filter"
      open={ids.length > 0 || search.has('topic') || search.has('tag') ? true : undefined}
    >
      <summary>筛选标签{ids.length ? `（${ids.length}）` : ''}</summary>
      {(search.has('topic') || search.has('tag')) && (
        <p className="muted">正在沿用旧链接的标签及类型范围。可清空后重新选择。</p>
      )}
      <TagSelector selected={ids} onChange={(next) => update(next)} />
      <div className="inline-form">
        <label>
          匹配方式{' '}
          <select
            aria-label="标签匹配方式"
            value={search.get('tag_match') || 'all'}
            onChange={(e) => update(ids, e.target.value)}
          >
            <option value="all">全部标签</option>
            <option value="any">任一标签</option>
          </select>
        </label>
        <button type="button" onClick={() => update([])}>
          清空标签筛选
        </button>
      </div>
    </details>
  )
}
