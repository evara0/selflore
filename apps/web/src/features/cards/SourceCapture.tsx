import { useLayoutEffect, useRef, useState } from 'react'
import { useApi } from '../../lib/workspace'

export type SourceSuggestions = Partial<{
  source_title: string
  source_author: string
  source_publisher: string
  source_platform: string
  source_published_on: string
}>
export type SourceResult = {
  category: 'webpage' | 'x'
  method: 'webpage' | 'x_oembed'
  status: 'success' | 'partial' | 'unavailable'
  fallback_reason: string | null
  fields: SourceSuggestions
}

export default function SourceCapture({
  url,
  onUrlChange,
  onApply,
  onBegin,
}: {
  url: string
  onUrlChange: (url: string) => void
  onApply: (fields: SourceSuggestions) => void
  onBegin?: () => void
}) {
  const api = useApi()
  const [mode, setMode] = useState('auto')
  const [state, setState] = useState({ busy: false, message: '' })
  const request = useRef(0)
  // Invalidate on every URL/mode transition, including A -> B -> A and unmount.
  useLayoutEffect(() => {
    request.current += 1
    return () => {
      request.current += 1
    }
  }, [url, mode])
  const [lastInput, setLastInput] = useState({ url, mode })
  if (lastInput.url !== url || lastInput.mode !== mode) {
    setLastInput({ url, mode })
    setState({ busy: false, message: '' })
  }
  async function capture() {
    const current = ++request.current
    if (!/^https?:\/\//i.test(url.trim())) {
      setState({ busy: false, message: '请先填写完整的 http:// 或 https:// 来源链接。' })
      return
    }
    setState({ busy: true, message: '正在获取来源信息…' })
    onBegin?.()
    try {
      const result = await api<SourceResult>('/sources/resolve', 'POST', { url: url.trim(), mode })
      if (current !== request.current) return
      onApply(result.fields)
      const method = result.method === 'x_oembed' ? 'X 公开信息' : '普通网页'
      const prefix = result.fallback_reason
        ? 'X 获取不可用，已回退普通网页。'
        : `获取方式：${method}。`
      const outcome =
        result.status === 'unavailable'
          ? '未获取到可用信息，请手动填写；仍可上传图片或摘录后保存。'
          : result.status === 'partial'
            ? '已获取部分信息，仅补全空白字段；缺失项可手动填写。'
            : '已获取来源信息，仅补全空白字段；请核对后保存。'
      setState({ busy: false, message: prefix + outcome })
    } catch {
      if (current !== request.current) return
      setState({ busy: false, message: '暂时无法获取来源，请稍后重试或手动填写，已有内容已保留。' })
    }
  }
  return (
    <section className="source-capture" aria-label="资料卡快速收录">
      <h3>粘贴链接，快速收录</h3>
      <label>
        收录链接
        <input
          type="url"
          maxLength={2048}
          value={url}
          placeholder="https://…"
          onChange={(e) => onUrlChange(e.target.value)}
        />
      </label>
      <div className="source-capture-actions">
        <label>
          获取方式
          <select aria-label="获取方式" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="auto">自动识别（网页 / X）</option>
            <option value="webpage">普通网页</option>
          </select>
        </label>
        <button type="button" disabled={state.busy || !url.trim()} onClick={() => void capture()}>
          {state.busy ? '获取中…' : '获取来源信息'}
        </button>
      </div>
      <p className="muted">
        点击获取将读取该公开链接；只补全空白字段，不更改分类、标签或图片作者。
      </p>
      <p role="status">{state.message}</p>
    </section>
  )
}
