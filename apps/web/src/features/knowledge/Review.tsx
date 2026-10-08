import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi, useData, useRefresh, params, type Unit, type Label } from '../../lib/workspace'
import { Markdown, PageHeading, QueryState } from '../../components/Common'

type Queue = { items: Unit[]; new_allowance: number; next_due_at: string | null }
type Preview = { intervals: { rating: number; seconds: number }[] }
function interval(seconds?: number) { if (seconds === undefined) return '…'; return seconds < 3600 ? `${Math.ceil(seconds / 60)} 分钟` : seconds < 86400 ? `${Math.round(seconds / 3600)} 小时` : `${Math.round(seconds / 86400)} 天` }
export default function Review() {
  const [search, setSearch] = useSearchParams(), queue = useData<Queue>(`/reviews/queue?${params({ topic_id: search.get('topic') })}`), topics = useData<{ items: Label[] }>('/topics?kind=knowledge')
  const api = useApi(), refresh = useRefresh(), unit = queue.data?.items[0]
  const preview = useData<Preview>(`/reviews/units/${unit?.id}/preview`, !!unit)
  const [revealed, setRevealed] = useState(false), [completed, setCompleted] = useState(0), [pending, setPending] = useState(false), [message, setMessage] = useState(''), [conflict, setConflict] = useState(false)
  const attempt = useRef<{ rating: number; id: string; duration: number } | null>(null), started = useRef(0)
  // A newly fetched unit starts a separate study interaction and timer.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { setRevealed(false); setMessage(''); setConflict(false); attempt.current = null; started.current = Date.now() }, [unit?.id, unit?.state_version])
  useEffect(() => { if (!unit && queue.data?.next_due_at) { const delay = Math.min(60000, Math.max(1000, new Date(queue.data.next_due_at).getTime() - Date.now())); const timer = window.setTimeout(() => void queue.refetch(), delay); return () => clearTimeout(timer) } }, [unit, queue])
  async function rate(rating: number) {
    if (!unit || !revealed || pending) return
    if (!attempt.current || attempt.current.rating !== rating) attempt.current = { rating, id: crypto.randomUUID(), duration: Math.min(3600000, Date.now() - started.current) }
    setPending(true); setMessage('')
    try { await api(`/reviews/units/${unit.id}/ratings`, 'POST', { request_id: attempt.current.id, rating, expected_state_version: unit.state_version, expected_content_revision: unit.card.revision, duration_ms: attempt.current.duration }); setCompleted(completed + 1); setRevealed(false); await refresh() }
    catch (e) { setMessage((e as Error).message); setConflict((e as { status?: number }).status === 409) }
    finally { setPending(false) }
  }
  return <><PageHeading title="今日复习" description="先回忆，再看答案。根据记忆的真实状态评价。"><Link to="/knowledge">结束本轮 ↗</Link></PageHeading><div className="study-toolbar"><span>本轮已完成 {completed} 个复习单元</span><select aria-label="复习分类" value={search.get('topic') || ''} onChange={e => setSearch(e.target.value ? { topic: e.target.value } : {})}><option value="">全部分类</option>{topics.data?.items.map(t => <option value={t.id} key={t.id}>{t.name}</option>)}</select></div><QueryState query={queue}>{unit ? <article className="study-card panel"><div className="card-meta"><span>{unit.state === 'new' ? '首次学习' : '到期复习'} · {unit.card.form === 'qa' ? '问答' : `填空 c${unit.cloze_index}`}</span><span>队列 {queue.data?.items.length} 个复习单元</span></div><h2>{unit.card.title}</h2><div className="study-content"><Markdown text={unit.question}/>{revealed && <div className="answer"><Markdown text={unit.answer}/></div>}</div>{!revealed ? <button className="primary" onClick={() => setRevealed(true)}>显示答案</button> : <div className="rating-grid">{['重来', '困难', '良好', '简单'].map((label, i) => <button className={`rating rating-${i + 1}`} key={label} disabled={pending || conflict} onClick={() => void rate(i + 1)}><b>{label}</b><small>{interval(preview.data?.intervals[i]?.seconds)}</small></button>)}</div>}<p role="status">{message}</p>{conflict && <button onClick={() => void queue.refetch()}>重新加载当前复习状态</button>}{preview.error && <QueryState query={preview}/>}</article> : <div className="state panel"><h2>这一轮已完成</h2><p>{queue.data?.next_due_at ? `下个学习单元到期：${new Date(queue.data.next_due_at).toLocaleTimeString('zh-CN')}` : '暂无到期复习单元。'}今日新单元剩余额度：{queue.data?.new_allowance}</p><button onClick={() => void queue.refetch()}>刷新队列</button><Link to="/knowledge">返回知识库</Link></div>}</QueryState></>
}
