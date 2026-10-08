// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Identity, clozeText, type Session } from './lib/workspace'
import { Markdown } from './components/Common'
import Knowledge from './features/knowledge/Knowledge'
import Review from './features/knowledge/Review'
import Opinions from './features/opinions/Opinions'
import Collections from './features/collections/Collections'

const user = { id: 'owner', username: 'alice', role: 'member', is_active: true, csrf_token: 'csrf' } as Session
const id = '11111111-1111-4111-8111-111111111111'
const card = { id, title: '主动回忆', code: 'K-1', kind: 'knowledge', form: 'qa', revision: 1, lifecycle: 'active', topics: [], tags: [], excerpt: '问题摘要', question_md: '主动回忆是什么？', answer_md: '独立于列表的真实答案' }
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
function mount(element: React.ReactNode, route = '/knowledge', path = '*') { const cache = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); render(<QueryClientProvider client={cache}><Identity value={{ session: user, openLogin: () => {}, refresh: async () => {} }}><MemoryRouter initialEntries={[route]}><Routes><Route path={path} element={element}/></Routes></MemoryRouter></Identity></QueryClientProvider>); return cache }
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
test('safe Markdown drops raw HTML, dangerous protocols and remote image loading', () => {
  mount(<Markdown text={'<script>alert(1)</script>\n\n[x](javascript:alert)\n\n![remote](https://example.com/a.png)\n\n`[[' + id + '|code]]`'}/>)
  expect(document.querySelector('script')).toBeNull()
  expect(document.querySelector('img')).toBeNull()
  expect(screen.getByText('x').getAttribute('href')).toBeNull()
  expect(screen.getByText('[图片暂不加载]')).toBeTruthy()
  expect(document.querySelector('code')?.textContent).toContain(id)
})
test('cloze hides all answers in reading and leaves code literals intact', () => {
  const value = '{{c1::答案::提示}} {{c2::第二个}} `{{c3::code}}`'
  expect(clozeText(value, false)).toBe('【提示】 【…】 `{{c3::code}}`')
  expect(clozeText(value, true)).toBe('答案 第二个 `{{c3::code}}`')
})
function knowledgeFetch() {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path.includes('/cards?')) return json({ items: [{ ...card, answer_md: undefined }], total: 1, offset: 0, limit: 12 })
    if (path === '/api/cards/' + id) return json(card)
    if (path === '/api/cards/summary') return json({ knowledge: 1 })
    if (path === '/api/reviews/summary') return json({ today_completed: 2, daily_review_goal: 20, due_units: 3, mastered_cards: 1 })
    return json({ items: [] })
  }))
}
test('knowledge hides answers until an explicit keyboard or touch action and labels real units', async () => {
  knowledgeFetch(); mount(<Knowledge/>)
  await screen.findByRole('link', { name: '主动回忆' })
  expect(screen.queryByText('独立于列表的真实答案')).toBeNull()
  const reveal = screen.getByRole('button', { name: /查看答案/ }); reveal.focus(); expect(document.activeElement).toBe(reveal)
  fireEvent.click(reveal)
  expect(await screen.findByText('独立于列表的真实答案')).toBeTruthy()
  expect(screen.getAllByText('个复习单元', { exact: false })).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: /收起答案/ }))
  expect(screen.queryByText('独立于列表的真实答案')).toBeNull()
})
test('knowledge network errors are retryable and never replaced with sample counts', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path.includes('/cards?') ? json({ detail: { message: '暂时失败' } }, 503) : json(path.includes('summary') ? {} : { items: [] })))
  mount(<Knowledge/>); expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('暂时失败'))
  expect(screen.getByRole('button', { name: '重试' })).toBeTruthy()
})
test('study cannot rate before revealing and a lost-response retry retains the same request id', async () => {
  const ratings: Record<string, unknown>[] = []; let complete = false
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: RequestInit) => {
    if (path.endsWith('/ratings')) { ratings.push(JSON.parse(init?.body as string)); if (ratings.length === 1) throw new Error('响应丢失'); complete = true; return json({}) }
    if (path.includes('/preview')) return json({ intervals: [1, 2, 3, 4].map(rating => ({ rating, seconds: rating * 600 })) })
    if (path.includes('/queue')) return json({ items: complete ? [] : [{ id: 'unit', card, question: '复习问题', answer: '复习答案', state: 'new', state_version: 1 }], new_allowance: 20 })
    return json({ items: [] })
  }))
  mount(<Review/>, '/knowledge/review')
  await screen.findByText('复习问题'); expect(screen.queryByRole('button', { name: /良好/ })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '显示答案' })); await screen.findByText('复习答案')
  fireEvent.click(screen.getByRole('button', { name: /良好/ })); await screen.findByText('响应丢失')
  fireEvent.click(screen.getByRole('button', { name: /良好/ })); await screen.findByText('本轮已完成 1 个复习单元')
  expect(ratings).toHaveLength(2); expect(ratings[0]).toEqual(ratings[1])
})
test('opinion selection restores from URL and does not show learning controls', async () => {
  const opinion = { ...card, kind: 'opinion', form: null, body_md: '一个独立观点', processing_state: 'inbox' }
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path === '/api/cards/' + id ? json(opinion) : path.endsWith('/links') ? json({ outgoing: [], incoming: [] }) : path.includes('/cards?') ? json({ items: [opinion], total: 1, limit: 12, offset: 0 }) : path.includes('summary') ? json({ opinions: 1 }) : json({ items: [] })))
  mount(<Opinions/>, '/opinions?card=' + id)
  expect(await screen.findByText('一个独立观点')).toBeTruthy()
  expect(screen.getByText('反向链接', { exact: false })).toBeTruthy()
  expect(screen.queryByRole('button', { name: '显示答案' })).toBeNull()
})
test('collection navigation resets revealed answers and never sends a rating', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    calls.push(path)
    if (path.endsWith('/items')) return json({ revision: 1, items: [{ ...card, item_id: 'first', position: 0 }, { ...card, id: 'secondcard', item_id: 'second', position: 1, title: '第二张', answer_md: '第二答案' }] })
    if (path.includes('/collections?')) return json({ items: [], total: 0 })
    return json({ id: 'group', title: '测试合集', revision: 1, total_items: 2, lifecycle: 'active' })
  }))
  mount(<Collections/>, '/collections/group?view=read&item=first', '/collections/:id')
  await screen.findByRole('heading', { name: '主动回忆' })
  expect(screen.getByRole('button', { name: '← 上一张' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: '显示答案' })); await screen.findByText('独立于列表的真实答案')
  fireEvent.click(screen.getByRole('button', { name: '下一张 →' })); await screen.findByRole('heading', { name: '第二张' })
  await waitFor(() => expect(screen.queryByText('第二答案')).toBeNull())
  expect(screen.getByRole('button', { name: '显示答案' })).toBeTruthy()
  expect(screen.getByRole('button', { name: '下一张 →' })).toHaveProperty('disabled', true)
  expect(calls.some(c => c.includes('rating'))).toBe(false)
})
test('reader uses the next available neighbor when a current item disappears on refresh', async () => {
  let removed = false
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path.endsWith('/items')) return json({ revision: removed ? 2 : 1, items: [
      { ...card, item_id: 'first', position: 0 },
      ...removed ? [] : [{ ...card, id: 'secondcard', item_id: 'second', title: '当前第二张', position: 1 }],
      { ...card, id: 'thirdcard', item_id: 'third', title: '下一位邻居', position: 2 },
    ] })
    if (path.includes('/collections?')) return json({ items: [], total: 0 })
    return json({ id: 'group', title: '测试合集', revision: 1, total_items: 3, lifecycle: 'active' })
  }))
  const cache = mount(<Collections/>, '/collections/group?view=read&item=second', '/collections/:id')
  await screen.findByRole('heading', { name: '当前第二张' }); removed = true
  await cache.invalidateQueries()
  expect(await screen.findByRole('heading', { name: '下一位邻居' })).toBeTruthy()
})
