import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { useData, cardUrl, type Label, type Card } from '../lib/workspace'

export function Icon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    book: <><path d="M12 5C7 2 3 3 3 5v14c4-2 7-1 9 1 2-2 5-3 9-1V5c0-2-4-3-9 0Z"/><path d="M12 5v15"/></>,
    card: <><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    link: <><path d="m10 14 4-4M8 16l-2 2a4 4 0 0 1-5-5l5-5a4 4 0 0 1 5 0M16 8l2-2a4 4 0 0 1 5 5l-5 5a4 4 0 0 1-5 0"/></>,
    search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></>,
    person: <><circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/></>,
    bookmark: <path d="M6 3h12v18l-6-4-6 4z"/>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 11h18"/></>,
    grid: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/></>,
  }
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.card}</svg>
}
export function PageHeading({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{description}</p></div><div className="heading-action">{children}</div></div>
}
export function QueryState({ query, empty = false, children }: { query: { isPending: boolean; error: Error | null; refetch: () => unknown }; empty?: boolean; children?: ReactNode }) {
  if (query.error) return <div className="state error" role="alert"><p>{query.error.message}</p><button onClick={() => query.refetch()}>重试</button></div>
  if (query.isPending) return <div className="state" role="status">正在加载…</div>
  if (empty) return <div className="state"><Icon name="card"/><h3>这里还没有卡片</h3><p>从一个问题或一个想法开始。</p><Link className="button" to="/new">新建卡片</Link></div>
  return children
}
export function Tags({ items }: { items?: Label[] }) { return <div className="tags">{items?.map(item => <span key={item.id} className="tag">{item.name}</span>)}</div> }
export function Pager({ total, offset, limit, onChange }: { total: number; offset: number; limit: number; onChange: (n: number) => void }) {
  return <div className="pager"><span>共 {total} 项</span><div><button aria-label="上一页" disabled={!offset} onClick={() => onChange(Math.max(0, offset - limit))}>‹</button><span>{Math.floor(offset / limit) + 1}</span><button aria-label="下一页" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>›</button></div></div>
}
function Reference({ id }: { id: string }) {
  const data = useData<Card>(`/cards/${id}`)
  if (!data.data || data.data.lifecycle !== 'active') return <span className="unavailable">[引用暂不可用]</span>
  return <Link to={cardUrl(data.data)}>{data.data.title}</Link>
}
export function Markdown({ text }: { text?: string }) {
  // Convert references outside Markdown code spans into a protocol handled only by our renderer.
  const value = (text || '').replace(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`]*`)|(\[\[([0-9a-f-]{36})(?:\|([^\]]*))?\]\])/gi,
    (_whole, code, _reference, id) => code || `[卡片引用](selflore:${id})`)
  return <div className="markdown"><ReactMarkdown skipHtml urlTransform={url => /^(https?:|mailto:|selflore:|\/)/i.test(url) ? url : ''} components={{
    img: () => <span className="muted">[图片暂不加载]</span>,
    a: ({ href, children }) => href?.startsWith('selflore:') ? <Reference id={href.slice(9)}/> : <a href={href || undefined} target="_blank" rel="noopener noreferrer">{children}</a>,
  }}>{value}</ReactMarkdown></div>
}
