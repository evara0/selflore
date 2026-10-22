import { useRef, useState, type FormEvent, type CSSProperties } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useApi, useRefresh, cardUrl, type Card, type MemoItem } from '../../lib/workspace'
import { PageHeading } from '../../components/Common'
import { CardPicker } from '../../components/Selectors'
import { EditorFrame, EditorTypes } from '../../components/EditorFrame'
import { useUnsaved } from '../../components/useUnsaved'
import CardSources, { type SourceFields } from './CardSources'
import CardForm from './CardForm'

const blankItem = (): MemoItem => ({
  id: crypto.randomUUID(),
  text: '',
  extra_values: ['', ''],
  is_completed: false,
  target_ids: [],
})
export default function MemoEditor({ original }: { original?: Card }) {
  const [query] = useSearchParams(),
    navigate = useNavigate(),
    api = useApi(),
    refresh = useRefresh()
  const [format, setFormat] = useState(
    original?.memo_format || (query.get('memo_format') === 'checklist' ? 'checklist' : 'note'),
  )
  const [title, setTitle] = useState(original?.title || ''),
    [body, setBody] = useState(original?.body_md || '')
  const [items, setItems] = useState<MemoItem[]>(() => original?.memo_items || [blankItem()])
  const [columns, setColumns] = useState(original?.memo_columns || ['条目', '字段 2', '字段 3'])
  const [count, setCount] = useState(original?.memo_column_count || 1)
  const [tags, setTags] = useState(original?.tag_ids || [])
  const [source, setSource] = useState<SourceFields>({
    sourceTitle: original?.source_title || '',
    sourceUrl: original?.source_url || '',
    locator: original?.source_locator || '',
    author: original?.source_author || '',
    publisher: original?.source_publisher || '',
    platform: original?.source_platform || '',
    published: original?.source_published_on || '',
  })
  const [message, setMessage] = useState(''),
    [pending, setPending] = useState(false),
    [dirty, setDirty] = useState(false)
  const [picker, setPicker] = useState<string | null>(null),
    [creating, setCreating] = useState<string | null>(null)
  const [created, setCreated] = useState<string[]>([]),
    [revision, setRevision] = useState(original?.revision)
  const attempt = useRef<{ json: string; id: string } | null>(null)
  const permit = useUnsaved(dirty)
  function update(id: string, values: Partial<MemoItem>) {
    setItems((old) => old.map((i) => (i.id === id ? { ...i, ...values } : i)))
    setDirty(true)
  }
  function move(index: number, direction: number) {
    const next = [...items]
    ;[next[index], next[index + direction]] = [next[index + direction], next[index]]
    setItems(next)
    setDirty(true)
  }
  function returnToRow(id: string) {
    setCreating(null)
    requestAnimationFrame(() => {
      const row = document.getElementById('edit-row-' + id)
      row?.scrollIntoView?.({ block: 'center' })
      row?.querySelector('textarea')?.focus()
    })
  }
  function linkKnowledge(id: string, card: Card) {
    setItems((old) =>
      old.map((i) =>
        i.id === id
          ? {
              ...i,
              target_ids: [...new Set([...i.target_ids, card.id])],
              targets: [...(i.targets || []).filter((t) => t.id !== card.id), card],
            }
          : i,
      ),
    )
    setDirty(true)
    setPicker(null)
  }
  async function save(event: FormEvent) {
    event.preventDefault()
    if (pending) return
    setPending(true)
    setMessage('')
    const content = {
      title,
      body_md: body || null,
      taxonomy_mode: 'unified',
      tag_ids: tags,
      source_url: source.sourceUrl || null,
      source_title: source.sourceTitle || null,
      source_locator: source.locator || null,
      source_author: source.author || null,
      source_publisher: source.publisher || null,
      source_platform: source.platform || null,
      source_published_on: source.published || null,
      memo_columns: columns,
      memo_column_count: count,
      memo_items:
        format === 'checklist'
          ? items.map((i) => ({
              id: i.id,
              text: i.text,
              extra_values: i.extra_values || ['', ''],
              is_completed: i.is_completed,
              target_ids: i.target_ids,
            }))
          : [],
    }
    const json = JSON.stringify(content)
    if (attempt.current?.json !== json) attempt.current = { json, id: crypto.randomUUID() }
    try {
      const saved = await api<Card>(
        original ? `/cards/${original.id}` : '/cards',
        original ? 'PATCH' : 'POST',
        original
          ? { ...content, expected_revision: revision }
          : {
              ...content,
              kind: 'memo',
              memo_format: format,
              client_request_id: attempt.current.id,
            },
      )
      permit()
      setDirty(false)
      await refresh()
      navigate(cardUrl(saved))
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setPending(false)
    }
  }
  async function reloadRevision() {
    try {
      const current = await api<Card>(`/cards/${original!.id}`)
      setRevision(current.revision)
      setMessage('已读取最新修订，输入保留。请在新窗口核对后再保存。')
    } catch (error) {
      setMessage((error as Error).message)
    }
  }
  return (
    <>
      <div hidden={!!creating}>
        <PageHeading title={original ? '编辑备忘' : '新建备忘'} />
        <EditorFrame
          cardId={original?.id}
          className="memo-editor"
          onSubmit={(e) => void save(e)}
          onChange={() => setDirty(true)}
          side={
            <CardSources
              kind="memo"
              topics={[]}
              tags={tags}
              source={source}
              onSourceChange={(field, value) => {
                setSource((old) => ({ ...old, [field]: value }))
                setDirty(true)
              }}
              onLabelsChange={(_t, next) => {
                setTags(next)
                setDirty(true)
              }}
            />
          }
        >
          <EditorTypes kind="memo" locked={!!original} />
          <label>
            备忘形式
            <select
              disabled={!!original}
              value={format}
              onChange={(e) => setFormat(e.target.value as 'note' | 'checklist')}
            >
              <option value="note">普通备忘</option>
              <option value="checklist">勾选清单</option>
            </select>
          </label>
          <label>
            标题
            <input
              required
              value={title}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="给这张卡片一个清晰的标题"
            />
          </label>
          <label>
            {format === 'note' ? '备忘正文（可选）' : '清单说明（可选）'}
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5} />
          </label>
          <button type="button" onClick={() => setPicker(picker === 'body' ? null : 'body')}>
            插入卡片引用
          </button>
          {picker === 'body' && (
            <CardPicker
              excluded={original ? [original.id] : []}
              onSelect={(c) => {
                setBody(body + '\n[[' + c.id + '|' + c.title + ']]')
                setPicker(null)
                setDirty(true)
              }}
            />
          )}
          {format === 'checklist' && (
            <>
              <div className="checklist-columns">
                <label>
                  显示字段数
                  <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                    {[1, 2, 3].map((n) => (
                      <option key={n} value={n}>
                        {n} 个字段
                      </option>
                    ))}
                  </select>
                </label>
                <p className="muted">
                  减少字段数仅隐藏，名称和内容会保留。首字段必填；勾选表示事项完成。
                </p>
                <div className="checklist-column-names">
                  {columns.slice(0, count).map((name, index) => (
                    <label key={index}>
                      字段 {index + 1} 名称
                      <input
                        required
                        maxLength={40}
                        value={name}
                        onChange={(e) =>
                          setColumns((old) => old.map((v, j) => (j === index ? e.target.value : v)))
                        }
                      />
                    </label>
                  ))}
                </div>
              </div>
              <ol
                className="memo-edit-items tabular-edit"
                style={{ '--memo-columns': count } as CSSProperties}
              >
                {items.map((item, index) => (
                  <li key={item.id} id={'edit-row-' + item.id}>
                    <div className="checklist-row-fields">
                      <label className="checklist-completion">
                        <input
                          type="checkbox"
                          checked={item.is_completed}
                          onChange={(e) => update(item.id, { is_completed: e.target.checked })}
                        />
                        已完成
                      </label>
                      {columns.slice(0, count).map((name, col) => (
                        <label key={col}>
                          {name || `字段 ${col + 1}`}
                          <textarea
                            aria-label={
                              col === 0 ? '条目 ' + (index + 1) : `条目 ${index + 1} ${name}`
                            }
                            required={col === 0}
                            rows={2}
                            maxLength={2000}
                            value={col === 0 ? item.text : item.extra_values?.[col - 1] || ''}
                            onChange={(e) =>
                              update(
                                item.id,
                                col === 0
                                  ? { text: e.target.value }
                                  : {
                                      extra_values: [0, 1].map((j) =>
                                        j === col - 1
                                          ? e.target.value
                                          : item.extra_values?.[j] || '',
                                      ),
                                    },
                              )
                            }
                          />
                        </label>
                      ))}
                    </div>
                    <div className="memo-item-actions">
                      <div
                        className="memo-item-order"
                        role="group"
                        aria-label={'排序条目 ' + (index + 1)}
                      >
                        <button
                          type="button"
                          aria-label={'上移条目 ' + (index + 1)}
                          disabled={!index}
                          onClick={() => move(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          aria-label={'下移条目 ' + (index + 1)}
                          disabled={index === items.length - 1}
                          onClick={() => move(index, 1)}
                        >
                          ↓
                        </button>
                      </div>
                      <div
                        className="memo-item-tools"
                        role="group"
                        aria-label={'条目操作 ' + (index + 1)}
                      >
                        <button
                          type="button"
                          disabled={items.length === 1}
                          onClick={() => {
                            setItems(items.filter((i) => i.id !== item.id))
                            setDirty(true)
                          }}
                        >
                          删除条目
                        </button>
                        <button
                          type="button"
                          disabled={item.target_ids.length >= 20}
                          onClick={() => setPicker(picker === item.id ? null : item.id)}
                        >
                          关联知识
                        </button>
                        <button
                          type="button"
                          disabled={item.target_ids.length >= 20}
                          onClick={() => {
                            setCreating(item.id)
                            setDirty(true)
                          }}
                        >
                          新建知识并关联
                        </button>
                      </div>
                    </div>
                    {item.targets?.map((t) => (
                      <div className="memo-targets" key={t.id}>
                        <Link to={cardUrl(t)} target="_blank">
                          {t.title} ↗
                        </Link>
                        <button
                          type="button"
                          aria-label={'移除关联 ' + t.title}
                          onClick={() =>
                            update(item.id, {
                              target_ids: item.target_ids.filter((id) => id !== t.id),
                              targets: item.targets?.filter((v) => v.id !== t.id),
                            })
                          }
                        >
                          移除
                        </button>
                      </div>
                    ))}
                    {picker === item.id && (
                      <CardPicker
                        kind="knowledge"
                        excluded={item.target_ids}
                        onSelect={(c) => linkKnowledge(item.id, c)}
                      />
                    )}
                  </li>
                ))}
              </ol>
              <button
                type="button"
                disabled={items.length >= 200}
                onClick={() => {
                  setItems([...items, blankItem()])
                  setDirty(true)
                }}
              >
                ＋ 添加条目
              </button>
            </>
          )}
          {!!created.length && (
            <p role="status" className="knowledge-save-status">
              已新建 {created.length}{' '}
              张知识并独立保存；清单及行关联尚未保存。请保存清单，失败可重试，知识不会被删除。
            </p>
          )}
          <p role="status" className="error-text">
            {message}
          </p>
          {original && message && (
            <p>
              <Link to={cardUrl(original)} target="_blank">
                在新窗口核对服务器内容
              </Link>{' '}
              <button type="button" onClick={() => void reloadRevision()}>
                核对后读取最新修订
              </button>
            </p>
          )}
          <div className="form-footer">
            <Link to={original ? cardUrl(original) : '/memos'}>取消</Link>
            <button className="primary" disabled={pending}>
              {pending ? '保存中…' : '保存备忘'}
            </button>
          </div>
        </EditorFrame>
      </div>
      {creating && (
        <section className="inline-knowledge" aria-label="当前行新建知识">
          <p className="muted">清单草稿已保留在本页。知识保存成功后会返回当前行，仍需保存清单。</p>
          <CardForm
            initialKind="knowledge"
            onCancel={() => returnToRow(creating)}
            onSaved={(card) => {
              linkKnowledge(creating, card)
              setCreated((old) => [...new Set([...old, card.id])])
              returnToRow(creating)
            }}
          />
        </section>
      )}
    </>
  )
}
