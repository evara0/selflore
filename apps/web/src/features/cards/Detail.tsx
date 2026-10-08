import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi, useData, useRefresh, useIdentity, cardUrl, clozeText, type Card } from '../../lib/workspace'
import { Icon, Markdown, QueryState, Tags } from '../../components/Common'
import { CardPicker } from '../../components/Selectors'

type Related = { id: string; title: string; kind: string; lifecycle: string; origins: string[] }
export function CardDetail({ id, compact = false }: { id: string; compact?: boolean }) {
  const query = useData<Card>(`/cards/${id}`), links = useData<{ outgoing: Related[]; incoming: Related[] }>(`/cards/${id}/links`)
  const api = useApi(), refresh = useRefresh()
  const { guest, openLogin } = useIdentity()
  const [revealed, setRevealed] = useState(false), [picker, setPicker] = useState(false), [message, setMessage] = useState('')
  const card = query.data
  async function mutate(path: string, method: string, body: object) { try { await api(path, method, body); setMessage(''); await refresh() } catch (e) { setMessage((e as Error).message) } }
  return <QueryState query={query}>{card && <article className={`card-detail ${compact ? 'compact' : 'panel'}`}>
    <div className="card-meta"><span>{card.kind === 'knowledge' ? '事实知识' : '原子观点'}</span><button aria-label={card.is_bookmarked ? '取消收藏' : '收藏卡片'} aria-pressed={card.is_bookmarked} onClick={() => void mutate(`/cards/${id}`, 'PATCH', { expected_revision: card.revision, is_bookmarked: !card.is_bookmarked })}><Icon name="bookmark"/></button></div>
    <h2>{card.title}</h2><small className="card-code">{card.code}</small><Tags items={[...card.topics, ...card.tags]}/>
    {card.lifecycle !== 'active' && <p className="notice">这张卡片已{card.lifecycle === 'trashed' ? '移入回收站' : '归档'}。</p>}
    {card.kind === 'opinion' ? <Markdown text={card.body_md}/> : <><Markdown text={card.form === 'qa' ? card.question_md : clozeText(card.body_md || '', revealed)}/>{card.form === 'qa' && revealed && <div className="answer"><span className="eyebrow">答案</span><Markdown text={card.answer_md}/></div>}<button className="reveal" onClick={() => setRevealed(!revealed)}>{revealed ? '隐藏答案' : '显示答案'}</button></>}
    {(card.source_title || card.source_url) && <div className="source">来源 · {card.source_url ? <a href={card.source_url} target="_blank" rel="noopener noreferrer">{card.source_title || card.source_url}</a> : card.source_title} {card.source_locator}</div>}
    <div className="detail-actions"><Link to={`/cards/${id}/edit`}>编辑卡片 ↗</Link>{card.kind === 'opinion' && <button onClick={() => void mutate(`/cards/${id}`, 'PATCH', { expected_revision: card.revision, processing_state: card.processing_state === 'inbox' ? 'organized' : 'inbox' })}>{card.processing_state === 'inbox' ? '标为已整理' : '移回待整理'}</button>}<button onClick={() => void mutate(`/cards/${id}/lifecycle`, 'POST', { expected_revision: card.revision, action: card.lifecycle === 'active' ? 'archive' : 'restore' })}>{card.lifecycle === 'active' ? '归档' : '恢复'}</button>{card.lifecycle !== 'trashed' && <button onClick={() => void mutate(`/cards/${id}/lifecycle`, 'POST', { expected_revision: card.revision, action: 'trash' })}>移入回收站</button>}</div>
    <p role="status" className="error-text">{message}</p>
    <section className="connections"><div className="section-title"><h3>关联卡片 <small>{links.data?.outgoing.length || 0}</small></h3><button aria-label="添加关联" onClick={() => guest ? openLogin() : setPicker(!picker)}>＋</button></div>{picker && <CardPicker excluded={[id]} onSelect={c => { void mutate(`/cards/${id}/links/${c.id}`, 'POST', { expected_revision: card.revision }); setPicker(false) }}/>}
      <QueryState query={links}>{links.data?.outgoing.map(c => <div className="connection-row" key={c.id}>{c.lifecycle === 'active' ? <Link to={cardUrl(c)}><Icon name={c.kind === 'knowledge' ? 'book' : 'link'}/>{c.title}</Link> : <span>{c.title} · 暂不可用</span>}{c.origins?.includes('manual') && <button aria-label={`移除关联 ${c.title}`} onClick={() => void mutate(`/cards/${id}/links/${c.id}`, 'DELETE', { expected_revision: card.revision })}>×</button>}</div>)}</QueryState>
      <h3>反向链接 <small>{links.data?.incoming.length || 0}</small></h3>{links.data?.incoming.map(c => <div className="connection-row" key={c.id}>{c.lifecycle === 'active' ? <Link to={cardUrl(c)}>{c.title} ↗</Link> : <span>{c.title} · 暂不可用</span>}</div>)}
    </section>
  </article>}</QueryState>
}
export default function DetailPage() { const { id } = useParams(); return <><Link className="back-link" to="/knowledge">← 返回知识</Link><CardDetail key={id} id={id!}/></> }
