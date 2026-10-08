import { useState } from 'react'
import { useApi, useData, useRefresh, params, type Card, type Page, type Label } from '../lib/workspace'
import { QueryState } from './Common'

export function CardPicker({ onSelect, excluded = [] }: { onSelect: (card: Card) => void; excluded?: string[] }) {
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const query = useData<Page<Card>>(`/cards?${params({ q, limit: 20, offset })}`)
  return <div className="card-picker"><input aria-label="搜索要关联的卡片" placeholder="搜索标题、内容或编号…" value={q} onChange={e => { setQ(e.target.value); setOffset(0) }}/><QueryState query={query}><div className="picker-results">{query.data?.items.filter(c => !excluded.includes(c.id)).map(c => <button type="button" key={c.id} onClick={() => onSelect(c)}><b>{c.title}</b><small>{c.kind === 'knowledge' ? '知识' : '观点'} · {c.code}</small></button>)}</div>{query.data && offset + 20 < query.data.total && <button type="button" onClick={() => setOffset(offset + 20)}>更多卡片</button>}</QueryState></div>
}

export function Labels({ kind, topics, tags, onChange }: { kind: string; topics: string[]; tags: string[]; onChange: (topics: string[], tags: string[]) => void }) {
  const topicQuery = useData<{ items: Label[] }>(`/topics?kind=${kind}`)
  const tagQuery = useData<{ items: Label[] }>('/tags')
  const api = useApi(), refresh = useRefresh()
  const [name, setName] = useState(''), [type, setType] = useState('topics'), [message, setMessage] = useState('')
  async function create() {
    try { const label = await api<Label>(`/${type}`, 'POST', { name, ...(type === 'topics' ? { kind } : {}) }); setName(''); onChange(type === 'topics' ? kind === 'knowledge' ? [label.id] : [...topics, label.id] : topics, type === 'tags' ? [...tags, label.id] : tags); await refresh() }
    catch (e) { setMessage((e as Error).message) }
  }
  function toggle(id: string, isTopic: boolean) {
    const selected = isTopic ? topics : tags
    const next = selected.includes(id) ? selected.filter(v => v !== id) : isTopic && kind === 'knowledge' ? [id] : [...selected, id]
    onChange(isTopic ? next : topics, isTopic ? tags : next)
  }
  return <div className="labels-editor"><span className="field-label">{kind === 'knowledge' ? '分类（最多一个）' : '主题'}</span><div className="choice-tags">{topicQuery.data?.items.map(t => <button type="button" className={topics.includes(t.id) ? 'selected' : ''} key={t.id} onClick={() => toggle(t.id, true)}>{t.name}</button>)}</div><span className="field-label">标签</span><div className="choice-tags">{tagQuery.data?.items.map(t => <button type="button" className={tags.includes(t.id) ? 'selected' : ''} key={t.id} onClick={() => toggle(t.id, false)}>{t.name}</button>)}</div><div className="inline-form"><select aria-label="新建分类或标签" value={type} onChange={e => setType(e.target.value)}><option value="topics">新分类 / 主题</option><option value="tags">新标签</option></select><input aria-label="分类或标签名称" value={name} maxLength={32} placeholder="名称" onChange={e => setName(e.target.value)}/><button type="button" disabled={!name.trim()} onClick={() => void create()}>添加</button></div><p role="status">{message}</p></div>
}
