import { useEffect, useRef, useState } from 'react'
import { useIdentity, type Attachment, type Card } from '../lib/workspace'
import { Markdown } from './Common'

export function PrivateImage({
  attachment,
  original = false,
}: {
  attachment: Attachment
  original?: boolean
}) {
  const { session, guest } = useIdentity()
  const [url, setUrl] = useState(''),
    [error, setError] = useState('')
  const source = guest
    ? attachment.demo_url || ''
    : `/api/attachments/${attachment.id}/content?variant=${original ? 'original' : 'thumbnail'}`
  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = ''
    if (guest) return () => controller.abort()
    fetch(source, { credentials: 'same-origin', signal: controller.signal, cache: 'no-store' })
      .then(async (response) => {
        if (response.status === 401) window.dispatchEvent(new Event('session-expired'))
        if (!response.ok) throw new Error('图片暂不可用，请重试或排查存储。')
        const blob = await response.blob()
        if (controller.signal.aborted) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError((e as Error).message)
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [source, session?.id, guest])
  if (error) return <span role="alert">{error}</span>
  const src = guest && source.startsWith('/demo/') ? source : url
  return src ? (
    <img
      className={original ? 'original-image' : 'attachment-thumb'}
      src={src}
      alt={attachment.alt_text || attachment.caption || '收录的图片'}
      loading={original ? 'eager' : 'lazy'}
    />
  ) : (
    <span role="status">图片加载中…</span>
  )
}

export function AttachmentGallery({ attachments = [] }: { attachments?: Attachment[] }) {
  const [selectedId, setSelected] = useState<string | null>(null)
  const selected = attachments.find((a) => a.id === selectedId) || null
  const activeSelection = selected?.id
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLElement | null>(null)
  const { session, guest } = useIdentity()
  useEffect(() => {
    if (activeSelection && !dialog.current?.open) dialog.current?.showModal()
    return () => trigger.current?.focus()
  }, [activeSelection])
  return (
    <div className="attachment-gallery">
      {attachments.map((a) => (
        <figure key={a.id}>
          <button
            type="button"
            className="image-button"
            aria-label={`放大图片 ${a.caption || a.alt_text || '查看原图'}`}
            onClick={(e) => {
              trigger.current = e.currentTarget
              setSelected(a.id)
            }}
          >
            <PrivateImage key={`${session?.id || 'guest'}:${a.id}`} attachment={a} />
          </button>
          <figcaption>
            {a.caption}
            {a.creator_name && <small>图片作者：{a.creator_name}</small>}
          </figcaption>
        </figure>
      ))}
      {selected && (
        <dialog
          className="image-dialog"
          ref={dialog}
          aria-label="图片原图"
          onClose={() => setSelected(null)}
          onClick={(e) => {
            if (e.target === e.currentTarget) dialog.current?.close()
          }}
        >
          <button type="button" className="image-close" onClick={() => dialog.current?.close()}>
            关闭原图 ×
          </button>
          <PrivateImage
            key={`${session?.id || (guest ? 'guest' : '')}:${selected.id}:original`}
            attachment={selected}
            original
          />
          <p>{selected.caption}</p>
        </dialog>
      )}
    </div>
  )
}

export function CardSource({ card }: { card: Card }) {
  return card.source_title ||
    card.source_url ||
    card.source_author ||
    card.source_publisher ||
    card.source_platform ||
    card.source_published_on ? (
    <div className="source">
      <div>
        来源 ·{' '}
        {card.source_url ? (
          <a href={card.source_url} target="_blank" rel="noopener noreferrer">
            {card.source_title || card.source_url}
          </a>
        ) : (
          card.source_title
        )}{' '}
        {card.source_locator}
      </div>
      {card.source_author && <div>来源作者：{card.source_author}</div>}
      {card.source_publisher && <div>发布／转载者：{card.source_publisher}</div>}
      {card.source_platform && <span>平台：{card.source_platform} </span>}
      {card.source_published_on && <span>发布日期：{card.source_published_on}</span>}
    </div>
  ) : null
}

export function ReferenceContent({ card }: { card: Card }) {
  return (
    <>
      <section className="reference-material">
        <h3>原始材料</h3>
        <Markdown text={card.body_md} />
        <AttachmentGallery
          key={`${card.id}:${card.attachments?.map((a) => a.id).join(',')}`}
          attachments={card.attachments}
        />
      </section>
      {card.note_md && (
        <section className="reference-note">
          <h3>我的说明</h3>
          <Markdown text={card.note_md} />
        </section>
      )}
      <CardSource card={card} />
    </>
  )
}
