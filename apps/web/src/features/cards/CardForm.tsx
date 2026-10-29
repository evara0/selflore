import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  useApi,
  useRefresh,
  cardUrl,
  clozeText,
  ApiError,
  type Card,
  type Attachment,
} from '../../lib/workspace'
import { Markdown, PageHeading } from '../../components/Common'
import { ImageUploader, type ImageUploaderHandle } from '../../components/ImageUploader'
import { AttachmentGallery } from '../../components/Attachments'
import { CardPicker } from '../../components/Selectors'
import { useUnsaved } from '../../components/useUnsaved'
import { EditorFrame, EditorTypes } from '../../components/EditorFrame'
import CardSources from './CardSources'
import SourceCapture from './SourceCapture'

type CardFormProps = {
  original?: Card
  initialKind?: string
  onSaved?: (card: Card) => void
  onCancel?: () => void
  onDirtyChange?: (dirty: boolean) => void
  onPermit?: () => void
}
export default function CardForm(props: CardFormProps) {
  return props.onSaved ? <CardFormEditor {...props} /> : <RoutedCardForm {...props} />
}
function RoutedCardForm(props: CardFormProps) {
  const [dirty, setDirty] = useState(false)
  const permit = useUnsaved(dirty)
  return <CardFormEditor {...props} onDirtyChange={setDirty} onPermit={permit} />
}
function CardFormEditor({
  original,
  initialKind = 'knowledge',
  onSaved,
  onCancel,
  onDirtyChange,
  onPermit,
}: CardFormProps) {
  const navigate = useNavigate(),
    api = useApi(),
    refresh = useRefresh()
  const [kind, setKind] = useState(original?.kind || initialKind),
    [form, setForm] = useState(original?.form || 'qa')
  const [title, setTitle] = useState(original?.title || ''),
    [question, setQuestion] = useState(original?.question_md || ''),
    [answer, setAnswer] = useState(original?.answer_md || ''),
    [body, setBody] = useState(original?.body_md || '')
  const [images, setImages] = useState<Attachment[]>(original?.attachments || []),
    [uploadBusy, setUploadBusy] = useState(false)
  const [note, setNote] = useState(original?.note_md || '')
  const [author, setAuthor] = useState(original?.source_author || ''),
    [publisher, setPublisher] = useState(original?.source_publisher || ''),
    [platform, setPlatform] = useState(original?.source_platform || ''),
    [published, setPublished] = useState(original?.source_published_on || '')
  const [sourceTitle, setSourceTitle] = useState(original?.source_title || ''),
    [sourceUrl, setSourceUrl] = useState(original?.source_url || ''),
    [locator, setLocator] = useState(original?.source_locator || '')
  const [topics, setTopics] = useState(original?.topic_ids || []),
    [tags, setTags] = useState(original?.tag_ids || [])
  const [picker, setPicker] = useState(false),
    [message, setMessage] = useState(''),
    [pending, setPending] = useState(false),
    [dirty, setDirty] = useState(false),
    [conflict, setConflict] = useState(false)
  const [revision, setRevision] = useState(original?.revision)
  const attempt = useRef<{ json: string; id: string } | null>(null)
  const uploader = useRef<ImageUploaderHandle>(null)
  const sourceTouched = useRef(new Set<string>())
  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])
  async function save(e: FormEvent) {
    e.preventDefault()
    if (pending) return
    if (uploadBusy) {
      setMessage('图片仍未完成，请重试或移除未完成项。')
      return
    }
    setPending(true)
    setMessage('')
    const content = {
      title,
      kind,
      form: kind === 'knowledge' ? form : null,
      question_md: kind === 'knowledge' && form === 'qa' ? question : null,
      answer_md: kind === 'knowledge' && form === 'qa' ? answer : null,
      body_md: kind === 'opinion' || kind === 'reference' || form === 'cloze' ? body || null : null,
      note_md: kind === 'reference' ? note || null : null,
      attachments:
        kind === 'reference'
          ? images.map((a) => ({
              id: a.id,
              caption: a.caption || '',
              alt_text: a.alt_text || '',
              creator_name: a.creator_name || null,
            }))
          : [],
      source_author: author || null,
      source_publisher: publisher || null,
      source_platform: platform || null,
      source_published_on: published || null,
      source_title: sourceTitle || null,
      source_url: sourceUrl || null,
      source_locator: locator || null,
      taxonomy_mode: 'unified',
      tag_ids: tags,
    }
    const json = JSON.stringify(content)
    if (attempt.current?.json !== json) attempt.current = { json, id: crypto.randomUUID() }
    try {
      const { kind: _kind, form: _form, ...editable } = content
      const card = await api<Card>(
        original ? `/cards/${original.id}` : '/cards',
        original ? 'PATCH' : 'POST',
        original
          ? { ...editable, expected_revision: revision }
          : { ...content, client_request_id: attempt.current!.id },
      )
      if (onSaved) {
        onSaved(card)
        return
      }
      onPermit?.()
      setDirty(false)
      await refresh()
      navigate(cardUrl(card))
    } catch (error) {
      setMessage((error as Error).message)
      setConflict(error instanceof ApiError && error.status === 409)
    } finally {
      setPending(false)
    }
  }
  async function resolve() {
    const current = await api<Card>(`/cards/${original!.id}`)
    setRevision(current.revision)
    setConflict(false)
    setMessage('已读取最新版本号，你的输入仍保留。请核对最新内容后再保存。')
  }
  return (
    <>
      <PageHeading title={onSaved ? '新建知识并关联' : original ? '编辑卡片' : '新建卡片'}>
        {!onSaved && <Link to="/collections/new">新建合集 ↗</Link>}
      </PageHeading>
      <EditorFrame
        cardId={original?.id}
        side={
          <CardSources
            kind={kind}
            topics={topics}
            tags={tags}
            source={{ sourceTitle, sourceUrl, locator, author, publisher, platform, published }}
            onSourceChange={(field, value) => {
              sourceTouched.current.add(field)
              const setters = {
                sourceTitle: setSourceTitle,
                sourceUrl: setSourceUrl,
                locator: setLocator,
                author: setAuthor,
                publisher: setPublisher,
                platform: setPlatform,
                published: setPublished,
              }
              setters[field](value)
              setDirty(true)
            }}
            onLabelsChange={(t, g) => {
              setTopics(t)
              setTags(g)
              setDirty(true)
            }}
          />
        }
        onSubmit={(e) => void save(e)}
        onChange={() => setDirty(true)}
        onPaste={(e) => {
          if (kind === 'reference' && !e.defaultPrevented && e.clipboardData.files.length) {
            e.preventDefault()
            uploader.current?.addFiles([...e.clipboardData.files])
            setDirty(true)
          }
        }}
      >
        <EditorTypes
          kind={kind}
          locked={!!original || !!onSaved}
          onChange={
            onSaved
              ? undefined
              : (k) => {
                  setKind(k)
                  setTopics([])
                }
          }
        />
        {kind === 'reference' && (
          <SourceCapture
            url={sourceUrl}
            onUrlChange={(value) => {
              setSourceUrl(value)
              setDirty(true)
            }}
            onApply={(fields) => {
              const fill = (
                field: string,
                setter: (update: (value: string) => string) => void,
                suggestion?: string,
              ) => {
                if (!sourceTouched.current.has(field))
                  setter((value) => (value.trim() ? value : suggestion || value))
              }
              fill('title', setTitle, fields.source_title)
              fill('sourceTitle', setSourceTitle, fields.source_title)
              fill('author', setAuthor, fields.source_author)
              fill('publisher', setPublisher, fields.source_publisher)
              fill('platform', setPlatform, fields.source_platform)
              fill('published', setPublished, fields.source_published_on)
              setDirty(true)
            }}
            onBegin={() => {
              sourceTouched.current = new Set()
            }}
          />
        )}
        <label>
          标题
          <input
            autoFocus={!!onSaved}
            required
            maxLength={200}
            value={title}
            placeholder="给这张卡片一个清晰的标题"
            onChange={(e) => {
              sourceTouched.current.add('title')
              setTitle(e.target.value)
            }}
          />
        </label>
        {kind === 'knowledge' && (
          <label>
            卡片形式
            <select
              disabled={!!original}
              value={form}
              onChange={(e) => setForm(e.target.value as 'qa' | 'cloze')}
            >
              <option value="qa">问答卡片</option>
              <option value="cloze">填空卡片</option>
            </select>
          </label>
        )}
        {kind === 'knowledge' && form === 'qa' ? (
          <>
            <label>
              问题
              <textarea
                required
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
              />
            </label>
            <label>
              答案
              <textarea
                required
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={6}
              />
            </label>
          </>
        ) : (
          <label>
            {kind === 'opinion' ? '观点正文' : kind === 'reference' ? '原始摘录' : '填空正文'}
            <textarea
              required={kind !== 'reference'}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={12}
              placeholder={
                kind === 'opinion'
                  ? '一次只说一个想法。支持 Markdown。'
                  : kind === 'reference'
                    ? '可粘贴原文摘录；上传图片时可留空。'
                    : '例如：主动回忆比 {{c1::重复阅读::学习方式}} 更有效。'
              }
            />
          </label>
        )}
        {kind === 'reference' && (
          <>
            <ImageUploader
              ref={uploader}
              images={images}
              onBusy={setUploadBusy}
              onChange={(next) => {
                setImages(next)
                setDirty(true)
              }}
            />
            <label>
              我的说明
              <textarea
                aria-label="我的说明"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={4}
                placeholder="写一句收录说明，不要求形成自己的观点。"
              />
            </label>
          </>
        )}
        {(kind === 'opinion' || kind === 'reference') && (
          <>
            <button type="button" onClick={() => setPicker(!picker)}>
              ＋ 插入卡片引用
            </button>
            {picker && (
              <CardPicker
                excluded={original ? [original.id] : []}
                onSelect={(c) => {
                  if (kind === 'reference') setNote(note + `\n[[${c.id}|${c.title}]]`)
                  else setBody(body + `\n[[${c.id}|${c.title}]]`)
                  setPicker(false)
                  setDirty(true)
                }}
              />
            )}
          </>
        )}
        <details>
          <summary>内容预览</summary>
          <Markdown
            text={
              kind === 'knowledge' && form === 'qa'
                ? question + '\n\n---\n\n' + answer
                : form === 'cloze' && kind === 'knowledge'
                  ? clozeText(body, false)
                  : body
            }
          />
          {kind === 'reference' && (
            <>
              <AttachmentGallery attachments={images} />
              <Markdown text={note} />
            </>
          )}
        </details>
        <p role="status" className="error-text">
          {message}
        </p>
        {conflict && (
          <div className="conflict">
            <p>
              服务器内容已变化。
              <Link to={cardUrl(original!)} target="_blank">
                在新窗口查看最新内容
              </Link>
            </p>
            <button type="button" onClick={() => void resolve()}>
              核对后使用最新版本号
            </button>
          </div>
        )}
        <div className="form-footer">
          {onCancel ? (
            <button
              type="button"
              disabled={pending}
              onClick={() => {
                if (!dirty || window.confirm('放弃这张尚未保存的知识？清单草稿会保留。')) onCancel()
              }}
            >
              取消新建知识
            </button>
          ) : (
            <Link to={original ? cardUrl(original) : '/cards'}>取消</Link>
          )}
          <button className="primary" type="submit" disabled={pending || uploadBusy}>
            {pending ? '保存中…' : '保存卡片'}
          </button>
        </div>
      </EditorFrame>
    </>
  )
}
