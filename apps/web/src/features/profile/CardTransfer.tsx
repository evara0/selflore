import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useIdentity } from '../../lib/workspace'
import './CardTransfer.css'

type Preview = { digest: string; card_count: number; asset_count: number }
type TransferError = { path: string; message: string; card_key?: string }

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function CardTransfer() {
  const { session, guest, openLogin } = useIdentity()
  const cache = useQueryClient()
  const [file, setFile] = useState<File>()
  const [preview, setPreview] = useState<Preview>()
  const [errors, setErrors] = useState<TransferError[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [format, setFormat] = useState('zip')
  const batch = useRef('')
  const pending = useRef(false)
  const fileInput = useRef<HTMLInputElement>(null)

  async function perform(action: 'validate' | 'import' | 'export') {
    if (!session || guest) {
      openLogin()
      return
    }
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setMessage('')
    setErrors([])
    try {
      const body = new FormData()
      if (action !== 'export') {
        if (!file) throw new Error('请先选择文件')
        body.set('file', file)
      }
      if (action === 'import') {
        if (!preview) throw new Error('请先预检文件')
        body.set('batch_id', batch.current)
        body.set('expected_digest', preview.digest)
      }
      const response = await fetch(
        `/api/card-transfer/${action}${action === 'export' ? `?format=${format}` : ''}`,
        {
          method: action === 'export' ? 'GET' : 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRF-Token': session.csrf_token },
          body: action === 'export' ? undefined : body,
        },
      )
      if (!response.ok) {
        if (response.status === 401) window.dispatchEvent(new Event('session-expired'))
        const payload = await response.json().catch(() => ({}))
        setErrors(payload.detail?.errors || [])
        if (action === 'validate') setPreview(undefined)
        throw new Error(payload.detail?.message || `请求失败 (${response.status})`)
      }
      if (action === 'export') {
        save(await response.blob(), `selflore-cards.${format}`)
        setMessage('完整导出已下载。请妥善保存文件。')
      } else if (action === 'validate') {
        setPreview(await response.json())
        setMessage('')
      } else {
        const result = await response.json()
        setCompleted(true)
        setPreview(undefined)
        setMessage(`导入成功：${result.card_count} 张卡片，${result.asset_count} 张图片。`)
        await cache.invalidateQueries()
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败，请重试')
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return (
    <section className="panel card-transfer" aria-label="卡片导入导出">
      <h2>卡片导入与导出</h2>
      <h3>批量导入</h3>
      <label>
        JSON或ZIP文件
        <input
          ref={fileInput}
          type="file"
          accept=".json,.zip,application/json,application/zip"
          disabled={busy}
          onChange={(event) => {
            setFile(event.target.files?.[0])
            setPreview(undefined)
            setErrors([])
            setMessage('')
            setCompleted(false)
            batch.current = crypto.randomUUID()
          }}
        />
      </label>
      {file && <p className="transfer-file">已选择：{file.name}</p>}
      {preview && (
        <p>
          预检内容：{preview.card_count} 张卡片，{preview.asset_count}{' '}
          张图片。确认后新增，不覆盖已有卡片。
        </p>
      )}
      <div className="transfer-actions">
        <button disabled={busy || !file || completed} onClick={() => void perform('validate')}>
          预检文件
        </button>
        <button
          className="primary"
          disabled={busy || !preview || completed}
          onClick={() => void perform('import')}
        >
          确认导入新卡片
        </button>
        {completed && (
          <button
            onClick={() => {
              setFile(undefined)
              setCompleted(false)
              setMessage('')
              if (fileInput.current) fileInput.current.value = ''
            }}
          >
            开始新批次
          </button>
        )}
      </div>
      <h3>完整导出</h3>
      <p>包含归档和回收站中的卡片。</p>
      <div className="transfer-actions">
        <label>
          导出格式
          <select value={format} disabled={busy} onChange={(e) => setFormat(e.target.value)}>
            <option value="zip">ZIP（推荐，包含原图）</option>
            <option value="json">JSON（仅无图片内容）</option>
          </select>
        </label>
        <button disabled={busy} onClick={() => void perform('export')}>
          导出全部卡片
        </button>
      </div>
      <p role="status" aria-live="polite">
        {busy ? '正在处理，请稍候…' : message}
      </p>
      {errors.length > 0 && (
        <ul className="transfer-errors" role="alert">
          {errors.map((error, i) => (
            <li key={i}>
              <strong>
                {error.card_key ? `${error.card_key} · ` : ''}
                {error.path}
              </strong>
              ：{error.message}
            </li>
          ))}
        </ul>
      )}
      <details className="transfer-help">
        <summary>格式与说明</summary>
        <div className="transfer-links">
          <a href="/api/card-transfer/guide" target="_blank" rel="noreferrer">
            JSON规范与AI提示词 ↗
          </a>
          <a href="/api/card-transfer/example" download="selflore-example.json">
            下载示例
          </a>
          <a href="/api/card-transfer/schema" download="v1.schema.json">
            下载JSON Schema
          </a>
        </div>
        <p>
          JSON适用于无图片内容；含图片请使用ZIP。每包最多2000张卡片，JSON最多32
          MiB，ZIP压缩和解压总量各最多512 MiB。
        </p>
        <p>
          导出保留卡片内容、标签、引用、清单及关联原图，不含合集结构、账号资料、复习历史与调度、活动日志或未关联图片。导入知识卡从新卡开始复习。
        </p>
        <p>同一批次重试不会重复创建；重新选择文件会开始新批次，再次导入相同内容会创建副本。</p>
      </details>
    </section>
  )
}
