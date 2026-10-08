import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApi, useData, useRefresh, cardUrl, clozeText, ApiError, type Card, type Collection } from '../../lib/workspace'
import { Markdown, PageHeading, QueryState } from '../../components/Common'
import { CardPicker, Labels } from '../../components/Selectors'

function useUnsaved(dirty: boolean) {
  const saved = useRef(false)
  const blocker = useBlocker(() => dirty && !saved.current)
  useEffect(() => { if (blocker.state === 'blocked') { if (window.confirm('内容尚未保存，确定离开？')) blocker.proceed(); else blocker.reset() } }, [blocker])
  useEffect(() => {
    function unload(e: BeforeUnloadEvent) { if (dirty && !saved.current) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', unload)
    return () => window.removeEventListener('beforeunload', unload)
  }, [dirty])
  return () => { saved.current = true }
}
export default function Editor() {
  const { id } = useParams(), [search] = useSearchParams()
  const query = useData<Card>(`/cards/${id}`, !!id)
  if (id) return <QueryState query={query}>{query.data && <CardForm key={id} original={query.data}/>}</QueryState>
  return <CardForm key={search.get('kind') || 'knowledge'} initialKind={search.get('kind') || 'knowledge'}/>
}
function CardForm({ original, initialKind = 'knowledge' }: { original?: Card; initialKind?: string }) {
  const navigate = useNavigate(), api = useApi(), refresh = useRefresh()
  const [kind, setKind] = useState(original?.kind || initialKind), [form, setForm] = useState(original?.form || 'qa')
  const [title, setTitle] = useState(original?.title || ''), [question, setQuestion] = useState(original?.question_md || ''), [answer, setAnswer] = useState(original?.answer_md || ''), [body, setBody] = useState(original?.body_md || '')
  const [sourceTitle, setSourceTitle] = useState(original?.source_title || ''), [sourceUrl, setSourceUrl] = useState(original?.source_url || ''), [locator, setLocator] = useState(original?.source_locator || '')
  const [topics, setTopics] = useState(original?.topic_ids || []), [tags, setTags] = useState(original?.tag_ids || [])
  const [picker, setPicker] = useState(false), [message, setMessage] = useState(''), [pending, setPending] = useState(false), [dirty, setDirty] = useState(false), [conflict, setConflict] = useState(false)
  const [revision, setRevision] = useState(original?.revision)
  const attempt = useRef<{ json: string; id: string } | null>(null)
  const permitLeave = useUnsaved(dirty)
  async function save(e: FormEvent) {
    e.preventDefault(); setPending(true); setMessage('')
    const content = { title, kind, form: kind === 'knowledge' ? form : null, question_md: kind === 'knowledge' && form === 'qa' ? question : null, answer_md: kind === 'knowledge' && form === 'qa' ? answer : null, body_md: kind === 'opinion' || form === 'cloze' ? body : null, source_title: sourceTitle || null, source_url: sourceUrl || null, source_locator: locator || null, topic_ids: topics, tag_ids: tags }
    const json = JSON.stringify(content)
    if (attempt.current?.json !== json) attempt.current = { json, id: crypto.randomUUID() }
    try {
      const { kind: _kind, form: _form, ...editable } = content
      const card = await api<Card>(original ? `/cards/${original.id}` : '/cards', original ? 'PATCH' : 'POST', original ? { ...editable, expected_revision: revision } : { ...content, client_request_id: attempt.current!.id })
      permitLeave(); setDirty(false); await refresh(); navigate(cardUrl(card))
    } catch (error) { setMessage((error as Error).message); setConflict(error instanceof ApiError && error.status === 409) }
    finally { setPending(false) }
  }
  async function resolve() { const current = await api<Card>(`/cards/${original!.id}`); setRevision(current.revision); setConflict(false); setMessage('已读取最新版本号，你的输入仍保留。请核对最新内容后再保存。'); }
  return <><PageHeading title={original ? '编辑卡片' : '新建卡片'} description="把知识留下，让想法发生连接。"><Link to="/collections/new">新建合集 ↗</Link></PageHeading><form className="editor panel" onSubmit={e => void save(e)} onChange={() => setDirty(true)}>
    <div className="editor-main"><div className="segmented">{['knowledge', 'opinion'].map(k => <button type="button" key={k} disabled={!!original} className={kind === k ? 'selected' : ''} onClick={() => { setKind(k); setTopics([]); setDirty(true) }}>{k === 'knowledge' ? '事实知识' : '原子观点'}</button>)}</div>
    <label>标题<input required maxLength={200} value={title} placeholder="给这张卡片一个清晰的标题" onChange={e => setTitle(e.target.value)}/></label>
    {kind === 'knowledge' && <label>卡片形式<select disabled={!!original} value={form} onChange={e => setForm(e.target.value as 'qa' | 'cloze')}><option value="qa">问答卡片</option><option value="cloze">填空卡片</option></select></label>}
    {kind === 'knowledge' && form === 'qa' ? <><label>问题<textarea required value={question} onChange={e => setQuestion(e.target.value)} rows={4}/></label><label>答案<textarea required value={answer} onChange={e => setAnswer(e.target.value)} rows={6}/></label></> : <label>{kind === 'opinion' ? '观点正文' : '填空正文'}<textarea required value={body} onChange={e => setBody(e.target.value)} rows={12} placeholder={kind === 'opinion' ? '一次只说一个想法。支持 Markdown。' : '例如：主动回忆比 {{c1::重复阅读::学习方式}} 更有效。'}/></label>}
    {kind === 'opinion' && <><button type="button" onClick={() => setPicker(!picker)}>＋ 插入卡片引用</button>{picker && <CardPicker excluded={original ? [original.id] : []} onSelect={c => { setBody(body + `\n[[${c.id}|${c.title}]]`); setPicker(false); setDirty(true) }}/>}</>}
    <details><summary>内容预览</summary><Markdown text={kind === 'knowledge' && form === 'qa' ? question + '\n\n---\n\n' + answer : form === 'cloze' && kind === 'knowledge' ? clozeText(body, false) : body}/></details>
    <p role="status" className="error-text">{message}</p>{conflict && <div className="conflict"><p>服务器内容已变化。<Link to={cardUrl(original!)} target="_blank">在新窗口查看最新内容</Link></p><button type="button" onClick={() => void resolve()}>核对后使用最新版本号</button></div>}
    <div className="form-footer"><Link to={original ? cardUrl(original) : '/knowledge'}>取消</Link><button className="primary" type="submit" disabled={pending}>{pending ? '保存中…' : '保存卡片'}</button></div></div>
    <aside className="editor-side"><h3>组织与来源</h3><Labels kind={kind} topics={topics} tags={tags} onChange={(t, g) => { setTopics(t); setTags(g); setDirty(true) }}/><label>来源标题<input value={sourceTitle} maxLength={200} onChange={e => setSourceTitle(e.target.value)}/></label><label>来源链接<input type="url" value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} placeholder="https://"/></label><label>页码 / 定位<input value={locator} maxLength={200} onChange={e => setLocator(e.target.value)}/></label><p className="muted">引用使用稳定 ID。修改标题后，连接仍然存在。</p></aside></form></>
}
export function CollectionEditor() {
  const api = useApi(), navigate = useNavigate(), refresh = useRefresh(), { id } = useParams()
  const query = useData<Collection>(`/collections/${id}`, !!id)
  const [title, setTitle] = useState(''), [description, setDescription] = useState(''), [style, setStyle] = useState('curve'), [color, setColor] = useState('sage'), [message, setMessage] = useState(''), [pending, setPending] = useState(false), [dirty, setDirty] = useState(false)
  const requestId = useRef(crypto.randomUUID())
  const permitLeave = useUnsaved(dirty)
  // Populate the form only when a server version is loaded or explicitly reloaded.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { if (query.data) { setTitle(query.data.title); setDescription(query.data.description_md); setStyle(query.data.cover_style); setColor(query.data.cover_color) } }, [query.data])
  async function save(e: FormEvent) { e.preventDefault(); setPending(true); try { const c = await api<Collection>(id ? `/collections/${id}` : '/collections', id ? 'PATCH' : 'POST', { title, description_md: description, cover_style: style, cover_color: color, ...(id ? { expected_revision: query.data!.revision } : { client_request_id: requestId.current }) }); permitLeave(); setDirty(false); await refresh(); navigate(`/collections/${c.id}`) } catch (error) { setMessage((error as Error).message) } finally { setPending(false) } }
  return <><PageHeading title={id ? '编辑合集' : '新建合集'} description="把相关的知识和观点放在一起。"/>{(!id || query.data) && <form className="panel single-form" onSubmit={e => void save(e)} onChange={() => setDirty(true)}><label>合集名称<input value={title} onChange={e => setTitle(e.target.value)} maxLength={200} required/></label><label>合集描述<textarea value={description} onChange={e => setDescription(e.target.value)} rows={5}/></label><label>封面样式<select value={style} onChange={e => setStyle(e.target.value)}><option value="curve">曲线</option><option value="lines">线条</option><option value="radial">放射</option></select></label><label>封面颜色<select value={color} onChange={e => setColor(e.target.value)}><option value="sage">鼠尾草绿</option><option value="clay">陶土</option></select></label><p role="status">{message}</p><button className="primary" disabled={pending}>保存合集</button>{id && <button type="button" onClick={() => void query.refetch()}>重新读取服务器内容</button>}</form>}{id && <QueryState query={query}/>}</>
}
