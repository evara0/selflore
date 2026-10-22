import { useState } from 'react'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'
import {
  useApi,
  useData,
  useRefresh,
  useIdentity,
  cardUrl,
  clozeText,
  cardKindName,
  type Card,
} from '../../lib/workspace'
import { CardImprint, Icon, Markdown, QueryState, Tags } from '../../components/Common'
import { ReferenceContent, CardSource } from '../../components/Attachments'
import { CardPicker } from '../../components/Selectors'

import MemoContent from '../../components/MemoContent'
import { cardInk } from '../../lib/theme'

type Related = {
  id: string
  title: string
  kind: string
  lifecycle: string
  origins: string[]
  item_links?: { memo_card_id: string; item_id: string }[]
}
export function CardDetail({ id, compact = false }: { id: string; compact?: boolean }) {
  const query = useData<Card>(`/cards/${id}`),
    links = useData<{ outgoing: Related[]; incoming: Related[] }>(`/cards/${id}/links`)
  const api = useApi(),
    refresh = useRefresh()
  const { guest, openLogin } = useIdentity()
  const [revealed, setRevealed] = useState(false),
    [picker, setPicker] = useState(false),
    [message, setMessage] = useState('')
  const card = query.data
  async function mutate(path: string, method: string, body: object) {
    try {
      await api(path, method, body)
      setMessage('')
      await refresh()
    } catch (e) {
      setMessage((e as Error).message)
    }
  }
  return (
    <QueryState query={query}>
      {card && (
        <div className={`detail-layout ${compact ? 'compact' : ''}`}>
          <article
            data-card-id={card.id}
            data-card-ink={cardInk(card.id)}
            className={`card-detail print-card ${compact ? 'compact' : 'panel'}`}
          >
            <div className="card-meta">
              <span>{cardKindName(card.kind)}</span>
              <button
                aria-label={card.is_bookmarked ? '取消收藏' : '收藏卡片'}
                aria-pressed={card.is_bookmarked}
                onClick={() =>
                  void mutate(`/cards/${id}`, 'PATCH', {
                    expected_revision: card.revision,
                    is_bookmarked: !card.is_bookmarked,
                  })
                }
              >
                <Icon name="bookmark" />
              </button>
            </div>
            <h2>{card.title}</h2>
            <small className="card-code">{card.code}</small>
            <Tags items={card.tags} />
            {card.lifecycle !== 'active' && (
              <p className="notice">
                这张卡片已{card.lifecycle === 'trashed' ? '移入回收站' : '归档'}。
              </p>
            )}
            {card.kind === 'memo' ? (
              <MemoContent card={card} />
            ) : card.kind === 'reference' ? (
              <ReferenceContent card={card} />
            ) : card.kind === 'opinion' ? (
              <Markdown text={card.body_md} />
            ) : (
              <>
                <Markdown
                  text={
                    card.form === 'qa' ? card.question_md : clozeText(card.body_md || '', revealed)
                  }
                />
                {card.form === 'qa' && revealed && (
                  <div className="answer">
                    <span className="eyebrow">答案</span>
                    <Markdown text={card.answer_md} />
                  </div>
                )}
                <button className="reveal" onClick={() => setRevealed(!revealed)}>
                  {revealed ? '隐藏答案' : '显示答案'}
                </button>
              </>
            )}
            {card.kind !== 'reference' && <CardSource card={card} />}
            <div className="detail-actions">
              <Link to={(card.kind === 'memo' ? '/memos/' : '/cards/') + id + '/edit'}>
                编辑卡片 ↗
              </Link>
              {card.kind !== 'knowledge' && (
                <button
                  onClick={() =>
                    void mutate(`/cards/${id}`, 'PATCH', {
                      expected_revision: card.revision,
                      processing_state: card.processing_state === 'inbox' ? 'organized' : 'inbox',
                    })
                  }
                >
                  {card.processing_state === 'inbox' ? '标为已整理' : '移回待整理'}
                </button>
              )}
              <button
                onClick={() =>
                  void mutate(`/cards/${id}/lifecycle`, 'POST', {
                    expected_revision: card.revision,
                    action: card.lifecycle === 'active' ? 'archive' : 'restore',
                  })
                }
              >
                {card.lifecycle === 'active' ? '归档' : '恢复'}
              </button>
              {card.lifecycle !== 'trashed' && (
                <button
                  onClick={() =>
                    void mutate(`/cards/${id}/lifecycle`, 'POST', {
                      expected_revision: card.revision,
                      action: 'trash',
                    })
                  }
                >
                  移入回收站
                </button>
              )}
            </div>
            <p role="status" className="error-text">
              {message}
            </p>
            <CardImprint code={card.code} />
          </article>
          <aside className="connections">
            <div className="section-title">
              <h3>
                关联卡片 <small>{links.data?.outgoing.length || 0}</small>
              </h3>
              <button
                aria-label="添加关联"
                onClick={() => (guest ? openLogin() : setPicker(!picker))}
              >
                ＋
              </button>
            </div>
            {picker && (
              <CardPicker
                excluded={[id]}
                onSelect={(c) => {
                  void mutate(`/cards/${id}/links/${c.id}`, 'POST', {
                    expected_revision: card.revision,
                  })
                  setPicker(false)
                }}
              />
            )}
            <QueryState query={links}>
              {links.data?.outgoing.map((c) => (
                <div className="connection-row print-card" data-card-ink={cardInk(c.id)} key={c.id}>
                  {c.lifecycle === 'active' ? (
                    <Link to={cardUrl(c)}>
                      <Icon name={c.kind === 'knowledge' ? 'book' : 'link'} />
                      {c.title}
                    </Link>
                  ) : (
                    <span>{c.title} · 暂不可用</span>
                  )}
                  {c.origins?.includes('manual') && (
                    <button
                      aria-label={`移除关联 ${c.title}`}
                      onClick={() =>
                        void mutate(`/cards/${id}/links/${c.id}`, 'DELETE', {
                          expected_revision: card.revision,
                        })
                      }
                    >
                      ×
                    </button>
                  )}
                  <small>{cardKindName(c.kind)}</small>
                  {c.item_links?.map((item) => (
                    <Link
                      key={item.item_id}
                      to={'/memos/' + item.memo_card_id + '?item=' + item.item_id}
                    >
                      定位条目 ↗
                    </Link>
                  ))}
                </div>
              ))}
            </QueryState>
            <h3>
              反向链接 <small>{links.data?.incoming.length || 0}</small>
            </h3>
            {links.data?.incoming.map((c) => (
              <div className="connection-row print-card" data-card-ink={cardInk(c.id)} key={c.id}>
                {c.lifecycle === 'active' ? (
                  <Link to={cardUrl(c)}>{c.title} ↗</Link>
                ) : (
                  <span>{c.title} · 暂不可用</span>
                )}
                <small>{cardKindName(c.kind)}</small>
                {c.item_links?.map((item) => (
                  <Link
                    key={item.item_id}
                    to={'/memos/' + item.memo_card_id + '?item=' + item.item_id}
                  >
                    定位条目 ↗
                  </Link>
                ))}
              </div>
            ))}
          </aside>
        </div>
      )}
    </QueryState>
  )
}
export default function DetailPage() {
  const { id } = useParams(),
    location = useLocation(),
    query = useData<Card>('/cards/' + id)
  const memo = location.pathname.startsWith('/memos')
  if (query.data?.kind === 'memo' && !memo)
    return <Navigate replace to={'/memos/' + id + location.search} />
  if (query.data && query.data.kind !== 'memo' && memo)
    return <Navigate replace to={'/cards/' + id} />
  const back = (location.state as { from?: string } | null)?.from || (memo ? '/memos' : '/cards')
  return (
    <>
      <Link className="back-link" to={back}>
        ← 返回{memo ? '备忘' : '卡片'}
      </Link>
      <CardDetail key={id} id={id!} />
    </>
  )
}
