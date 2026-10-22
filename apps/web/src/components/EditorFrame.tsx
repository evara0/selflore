import type { ComponentProps, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { cardInk } from '../lib/theme'

export function EditorFrame({
  side,
  children,
  cardId,
  ...props
}: ComponentProps<'form'> & {
  side: ReactNode
  cardId?: string
}) {
  return (
    <form
      {...props}
      className={'editor panel ' + (props.className || '')}
      data-card-ink={cardInk(cardId)}
    >
      <div className="editor-main">{children}</div>
      {side}
    </form>
  )
}

export function EditorTypes({
  kind,
  locked,
  onChange,
}: {
  kind: string
  locked?: boolean
  onChange?: (kind: string) => void
}) {
  return (
    <div className="segmented" aria-label="卡片类型">
      {['knowledge', 'opinion', 'reference', 'memo'].map((k) =>
        onChange && k !== 'memo' ? (
          <button
            key={k}
            type="button"
            disabled={locked}
            className={kind === k ? 'selected' : ''}
            onClick={() => onChange(k)}
          >
            {k === 'knowledge' ? '事实知识' : k === 'reference' ? '资料卡' : '观点'}
          </button>
        ) : kind === k ? (
          <span key={k} className="selected">
            {k === 'memo' ? '备忘 / 清单' : '事实知识'}
          </span>
        ) : locked ? (
          <span key={k} className="muted">
            {k === 'knowledge'
              ? '事实知识'
              : k === 'reference'
                ? '资料卡'
                : k === 'memo'
                  ? '备忘 / 清单'
                  : '观点'}
          </span>
        ) : (
          <Link key={k} to={'/new?kind=' + k}>
            {k === 'knowledge'
              ? '事实知识'
              : k === 'reference'
                ? '资料卡'
                : k === 'memo'
                  ? '备忘 / 清单'
                  : '观点'}
          </Link>
        ),
      )}
    </div>
  )
}
