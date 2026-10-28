import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Markdown, PageHeading } from '../../components/Common'
import { AttachmentGallery } from '../../components/Attachments'
import { useUnsaved } from '../../components/useUnsaved'
import {
  cardKindName,
  cardUrl,
  useApi,
  useRefresh,
  type Attachment,
  type Card,
  type MemoItem,
} from '../../lib/workspace'

type ImportContent = {
  kind: Card['kind']
  title: string
  form: Card['form']
  memo_format: 'note' | 'checklist' | null
  body_md: string | null
  note_md: string | null
  question_md: string | null
  answer_md: string | null
  memo_items: MemoItem[]
  memo_columns: string[]
  memo_column_count: number
  tag_ids: string[]
  attachments: Attachment[]
  [key: string]: unknown
}
type Prepared = { content: ImportContent; source: string; requestId: string }
const maxBytes = 1024 * 1024
const sourceFields = [
  ['source_title', '来源标题'],
  ['source_url', '来源链接'],
  ['source_locator', '页码 / 定位'],
  ['source_author', '来源作者'],
  ['source_publisher', '发布／转载者'],
  ['source_platform', '来源平台'],
  ['source_published_on', '发布日期'],
]

export default function JsonImport() {
  const api = useApi(),
    refresh = useRefresh(),
    navigate = useNavigate()
  const [text, setText] = useState(''),
    [fileName, setFileName] = useState('')
  const [prepared, setPrepared] = useState<Prepared | null>(null)
  const [busy, setBusy] = useState<'file' | 'preview' | 'save' | null>(null)
  const [message, setMessage] = useState('')
  const active = useRef(true),
    operation = useRef(false)
  const permit = useUnsaved(!!text.trim())
  const previewHeading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    active.current = true
    return () => {
      active.current = false
    }
  }, [])
  function update(value: string) {
    setText(value)
    setPrepared(null)
    setMessage('')
  }
  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || operation.current) return
    setPrepared(null)
    setMessage('')
    if (file.size > maxBytes) {
      setMessage('JSON 文件不能超过 1 MiB。')
      return
    }
    operation.current = true
    setBusy('file')
    try {
      const bytes = await file.arrayBuffer()
      if (!active.current) return
      let content: string
      try {
        content = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
      } catch {
        throw new Error('请使用 UTF-8 编码的 JSON 文件。')
      }
      update(content.replace(/^\ufeff/, ''))
      setFileName(file.name)
    } catch (error) {
      if (active.current) setMessage((error as Error).message || '文件读取失败，请重试。')
    } finally {
      operation.current = false
      if (active.current) setBusy(null)
    }
  }
  async function prepare(event: FormEvent) {
    event.preventDefault()
    if (operation.current || !text.trim()) return
    if (new TextEncoder().encode(text).length > maxBytes) {
      setPrepared(null)
      setMessage('JSON 内容不能超过 1 MiB。')
      return
    }
    if (prepared?.source === text) {
      previewHeading.current?.focus()
      return
    }
    operation.current = true
    setBusy('preview')
    setMessage('')
    try {
      const content = await api<ImportContent>('/cards/import-preview', 'POST', { json_text: text })
      if (!active.current) return
      setPrepared({ content, source: text, requestId: crypto.randomUUID() })
      requestAnimationFrame(() => previewHeading.current?.focus())
    } catch (error) {
      if (active.current) {
        setPrepared(null)
        setMessage((error as Error).message)
      }
    } finally {
      operation.current = false
      if (active.current) setBusy(null)
    }
  }
  async function save() {
    if (!prepared || operation.current) return
    operation.current = true
    setBusy('save')
    setMessage('')
    try {
      const card = await api<Card>('/cards', 'POST', {
        ...prepared.content,
        client_request_id: prepared.requestId,
      })
      if (!active.current) return
      permit()
      void refresh()
      navigate(cardUrl(card))
    } catch (error) {
      if (active.current) setMessage((error as Error).message)
    } finally {
      operation.current = false
      if (active.current) setBusy(null)
    }
  }
  const content = prepared?.content
  return (
    <>
      <PageHeading title="JSON 导入" description="由内容自动识别卡片类别，预览确认后保存。" />
      <div className="json-import">
        <section className="panel import-input" aria-label="导入内容">
          <h2>选择文件或粘贴内容</h2>
          <p className="muted">每次导入一张卡片，支持 UTF-8 JSON 文件，最大 1 MiB。</p>
          <label>
            选择 JSON 文件
            <input
              type="file"
              accept=".json,application/json"
              disabled={!!busy}
              onChange={(e) => void readFile(e)}
            />
          </label>
          {fileName && <p className="muted import-filename">已读取：{fileName}</p>}
          <form onSubmit={(event) => void prepare(event)}>
            <label>
              JSON 内容
              <textarea
                spellCheck={false}
                rows={14}
                value={text}
                disabled={!!busy}
                placeholder={
                  '{\n  "kind": "memo",\n  "memo_format": "checklist",\n  "title": "我的清单",\n  "memo_items": [{ "text": "阅读一篇论文" }]\n}'
                }
                onChange={(event) => {
                  update(event.target.value)
                  setFileName('')
                }}
              />
            </label>
            <button type="submit" disabled={!!busy || !text.trim()}>
              {busy === 'preview' ? '正在校验…' : '校验并预览'}
            </button>
          </form>
          <details className="import-help">
            <summary>JSON 格式与示例</summary>
            <p>
              kind
              指定类别：knowledge（事实知识）、opinion（观点）、reference（资料卡）、memo（备忘）。
            </p>
            <p>事实知识需指定 form 为 qa 或 cloze；备忘需指定 memo_format 为 note 或 checklist。</p>
            <p>
              标题使用 title，说明或正文使用 body_md。清单行用 text 保存首列，extra_values
              保存第二、三列，行 ID 可省略。
            </p>
            <p>
              <a href="/examples/paper-reading-checklist.json" download>
                下载三字段论文阅读需求清单示例
              </a>
            </p>
          </details>
          {busy === 'file' && <p role="status">正在读取文件…</p>}
          {message && !prepared && (
            <p className="error-text" role="alert">
              {message}
            </p>
          )}
        </section>
        <section className="panel import-preview" aria-label="导入预览">
          <h2 ref={previewHeading} tabIndex={-1}>
            导入预览
          </h2>
          {!content ? (
            <p className="muted">选择文件或粘贴 JSON 后，点击“校验并预览”。确认前不会创建卡片。</p>
          ) : (
            <>
              <p className="eyebrow">
                {cardKindName(content.kind)}
                {content.kind === 'memo'
                  ? content.memo_format === 'checklist'
                    ? ' · 清单'
                    : ' · 普通备忘'
                  : content.kind === 'knowledge'
                    ? content.form === 'qa'
                      ? ' · 问答'
                      : ' · 填空'
                    : ''}
              </p>
              <h3 className="import-title">{content.title}</h3>
              {content.kind === 'knowledge' && content.form === 'qa' ? (
                <>
                  <h4>问题</h4>
                  <Markdown text={content.question_md || ''} />
                  <h4>答案</h4>
                  <Markdown text={content.answer_md || ''} />
                </>
              ) : (
                <Markdown text={content.body_md || ''} />
              )}
              {content.kind === 'reference' && (
                <>
                  <AttachmentGallery attachments={content.attachments} />
                  {content.note_md && (
                    <>
                      <h4>我的说明</h4>
                      <Markdown text={content.note_md} />
                    </>
                  )}
                </>
              )}
              {content.memo_format === 'checklist' && (
                <>
                  <p className="muted">
                    {content.memo_items.length} 个条目 · {content.memo_column_count} 个显示字段
                  </p>
                  <ol className="import-items">
                    {content.memo_items.map((item) => (
                      <li key={item.id}>
                        <p className="muted">{item.is_completed ? '已完成' : '未完成'}</p>
                        <dl className="import-fields">
                          {content.memo_columns.map((column, index) => (
                            <div key={index}>
                              <dt>
                                {column}
                                {index >= content.memo_column_count ? '（保存后隐藏）' : ''}
                              </dt>
                              <dd>
                                {(index === 0 ? item.text : item.extra_values?.[index - 1]) || '—'}
                              </dd>
                            </div>
                          ))}
                        </dl>
                        {item.target_ids.length > 0 && (
                          <p className="muted">关联卡片：{item.target_ids.join('、')}</p>
                        )}
                      </li>
                    ))}
                  </ol>
                </>
              )}
              {sourceFields.some(([key]) => !!content[key]) && (
                <dl className="import-source">
                  {sourceFields
                    .filter(([key]) => !!content[key])
                    .map(([key, label]) => (
                      <div key={key}>
                        <dt>{label}</dt>
                        <dd>{String(content[key])}</dd>
                      </div>
                    ))}
                </dl>
              )}
              {content.tag_ids.length > 0 && (
                <p className="muted">标签 ID：{content.tag_ids.join('、')}。保存时核对账号归属。</p>
              )}
              {content.kind !== 'memo' && (
                <p className="muted">
                  {content.processing_state === 'organized' ? '已整理' : '待整理'}
                  {content.is_bookmarked ? ' · 已收藏' : ''}
                </p>
              )}
              {message && (
                <p className="error-text" role="alert">
                  {message}
                </p>
              )}
              <p className="muted">
                确认后将新建这张{cardKindName(content.kind)}卡片，可在详情页继续编辑。
              </p>
              <div className="import-actions">
                <button className="primary" disabled={!!busy} onClick={() => void save()}>
                  {busy === 'save' ? '正在导入…' : '确认导入'}
                </button>
                <Link to="/cards">取消</Link>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  )
}
