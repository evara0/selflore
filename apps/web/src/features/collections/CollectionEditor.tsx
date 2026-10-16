import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useApi, useData, useRefresh, type Collection } from '../../lib/workspace'
import { PageHeading, QueryState } from '../../components/Common'
import { useUnsaved } from '../../components/useUnsaved'

export default function CollectionEditor() {
  const api = useApi(),
    navigate = useNavigate(),
    refresh = useRefresh(),
    { id } = useParams()
  const query = useData<Collection>(`/collections/${id}`, !!id)
  const [title, setTitle] = useState(''),
    [description, setDescription] = useState(''),
    [style, setStyle] = useState('curve'),
    [color, setColor] = useState('sage'),
    [message, setMessage] = useState(''),
    [pending, setPending] = useState(false),
    [dirty, setDirty] = useState(false)
  const requestId = useRef(crypto.randomUUID())
  const permitLeave = useUnsaved(dirty)
  // Populate the form only when a server version is loaded or explicitly reloaded.
  /* oxlint-disable react/set-state-in-effect */
  useEffect(() => {
    if (query.data) {
      setTitle(query.data.title)
      setDescription(query.data.description_md)
      setStyle(query.data.cover_style)
      setColor(query.data.cover_color)
    }
  }, [query.data])
  /* oxlint-enable react/set-state-in-effect */
  async function save(e: FormEvent) {
    e.preventDefault()
    setPending(true)
    try {
      const c = await api<Collection>(
        id ? `/collections/${id}` : '/collections',
        id ? 'PATCH' : 'POST',
        {
          title,
          description_md: description,
          cover_style: style,
          cover_color: color,
          ...(id
            ? { expected_revision: query.data!.revision }
            : { client_request_id: requestId.current }),
        },
      )
      permitLeave()
      setDirty(false)
      await refresh()
      navigate(`/collections/${c.id}`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setPending(false)
    }
  }
  return (
    <>
      <PageHeading title={id ? '编辑合集' : '新建合集'} />
      {(!id || query.data) && (
        <form
          className="panel single-form"
          onSubmit={(e) => void save(e)}
          onChange={() => setDirty(true)}
        >
          <label>
            合集名称
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              required
            />
          </label>
          <label>
            合集描述
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
            />
          </label>
          <label>
            封面样式
            <select value={style} onChange={(e) => setStyle(e.target.value)}>
              <option value="curve">曲线</option>
              <option value="lines">线条</option>
              <option value="radial">放射</option>
            </select>
          </label>
          <label>
            封面颜色
            <select value={color} onChange={(e) => setColor(e.target.value)}>
              <option value="sage">鼠尾草绿</option>
              <option value="clay">陶土</option>
            </select>
          </label>
          <p role="status">{message}</p>
          <button className="primary" disabled={pending}>
            保存合集
          </button>
          {id && (
            <button type="button" onClick={() => void query.refetch()}>
              重新读取服务器内容
            </button>
          )}
        </form>
      )}
      {id && <QueryState query={query} />}
    </>
  )
}
