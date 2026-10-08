// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { readDemo, demoId } from './lib/demo'
import type { Card, Page, Profile } from './lib/workspace'

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const calls: string[] = []
function guestFetch() {
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: RequestInit) => {
    calls.push(`${init?.method || 'GET'} ${path}`)
    if (path === '/api/auth/config') return json({ registration_enabled: true })
    if (path === '/api/auth/me') return json({ detail: '请先登录' }, 401)
    throw new Error(`Guest attempted a real API: ${path}`)
  }))
}
beforeEach(() => {
  calls.length = 0
  history.replaceState(null, '', '/knowledge')
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event('close')) }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('guest cards hide answers, filter locally and gate bookmark without any write request', async () => {
  guestFetch(); render(<App/>)
  expect(await screen.findByText('演示空间 · 只读')).toBeTruthy()
  await screen.findByRole('link', { name: '主动回忆为什么有效？' })
  expect(screen.queryByText(/主动回忆是先不看材料/)).toBeNull()
  fireEvent.change(screen.getByLabelText('搜索知识'), { target: { value: '主动回忆为什么' } })
  await waitFor(() => expect(screen.getAllByRole('button', { name: /查看答案/ })).toHaveLength(1))
  fireEvent.click(screen.getByRole('button', { name: /查看答案/ }))
  expect(await screen.findByText(/主动回忆是先不看材料/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '取消收藏 主动回忆为什么有效？' }))
  await waitFor(() => expect(screen.getByRole('dialog').hasAttribute('open')).toBe(true))
  expect(screen.getByRole('tab', { name: '注册' })).toBeTruthy()
  expect(calls.every(c => c.startsWith('GET /api/auth/'))).toBe(true)
})

test('guest reader resets revealed answers and navigation follows stable opinion links', async () => {
  history.replaceState(null, '', `/collections/${demoId(301)}?view=read`)
  guestFetch(); render(<App/>)
  await screen.findByRole('heading', { name: '主动回忆为什么有效？' })
  fireEvent.click(screen.getByRole('button', { name: '显示答案' }))
  expect(await screen.findByText(/主动回忆是先不看材料/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '下一张 →' }))
  await screen.findByRole('heading', { name: '用填空记住学习过程' })
  expect(screen.queryByText(/主动提取/)).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '显示答案' }))
  expect(await screen.findByText(/主动提取/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '下一张 →' }))
  await screen.findByRole('heading', { name: '笔记的价值在于连接' })
  fireEvent.click((await screen.findAllByRole('link', { name: '主动回忆为什么有效？' }))[0])
  await waitFor(() => expect(location.pathname).toBe(`/knowledge/cards/${demoId(1)}`))
  expect(screen.queryByText(/主动回忆是先不看材料/)).toBeNull()
  expect(calls.every(c => c.startsWith('GET /api/auth/'))).toBe(true)
})

test.each(['/new', '/knowledge/review', '/settings', '/admin/users', `/cards/${demoId(1)}/edit`, '/collections/new'])('guest protected route %s prompts authentication without loading a write form', async path => {
  history.replaceState(null, '', path)
  guestFetch(); render(<App/>)
  expect(await screen.findByRole('heading', { name: '在自己的空间继续' })).toBeTruthy()
  await waitFor(() => expect(screen.getByRole('dialog').hasAttribute('open')).toBe(true))
  expect(screen.queryByRole('button', { name: '保存卡片' })).toBeNull()
  expect(calls.every(c => c.startsWith('GET /api/auth/'))).toBe(true)
})

test('login removes samples and expired session removes private profile from the screen', async () => {
  let loggedIn = false
  const session = { id: 'private-user', username: 'privateuser', role: 'member', is_active: true, csrf_token: 'test-token' }
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: RequestInit) => {
    calls.push(`${init?.method || 'GET'} ${path}`)
    if (path === '/api/auth/config') return json({ registration_enabled: true })
    if (path === '/api/auth/me') return loggedIn ? json(session) : json({}, 401)
    if (path === '/api/auth/login') { loggedIn = true; return json(session) }
    if (path === '/api/auth/logout') { loggedIn = false; return new Response(null, { status: 204 }) }
    if (path === '/api/me/profile') return json({ ...readDemo<Profile>('/me/profile'), display_name: '私有资料', username: 'privateuser', bio: '只属于账号的资料' })
    if (path.startsWith('/api/cards?')) return json({ items: [], total: 0, limit: 12, offset: 0 })
    return json(readDemo(path.slice(4)))
  }))
  render(<App/>)
  await screen.findByRole('link', { name: '主动回忆为什么有效？' })
  fireEvent.click(screen.getByRole('button', { name: '登录' }))
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'privateuser' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'long-password-123' } })
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登录' }))
  await screen.findByRole('button', { name: /privateuser/ })
  expect(screen.queryByText('演示空间 · 只读')).toBeNull()
  await waitFor(() => expect(screen.queryByRole('link', { name: '主动回忆为什么有效？' })).toBeNull())
  fireEvent.click(within(screen.getByRole('navigation', { name: '主导航' })).getByRole('link', { name: '我的' }))
  await screen.findByRole('heading', { name: '私有资料' })
  fireEvent(window, new Event('session-expired'))
  await screen.findByRole('heading', { name: '演示账号' })
  expect(screen.queryByText('只属于账号的资料')).toBeNull()
  expect(calls.filter(c => !c.startsWith('GET')).every(c => c === 'POST /api/auth/login')).toBe(true)
})

test('demo results are isolated copies, masked summaries and unknown IDs never leak another card', () => {
  const listed = readDemo<Page<Card>>('/cards?kind=knowledge&limit=2&offset=1')
  expect(listed.items).toHaveLength(2); expect(listed.total).toBe(6)
  expect(listed.items.every(c => c.answer_md === undefined && c.body_md === undefined)).toBe(true)
  const cloze = readDemo<Page<Card>>('/cards?kind=knowledge&q=用填空').items[0]
  expect(cloze.excerpt).not.toContain('主动提取')
  const card = readDemo<Card>(`/cards/${demoId(1)}`); card.title = 'changed'
  expect(readDemo<Card>(`/cards/${demoId(1)}`).title).toBe('主动回忆为什么有效？')
  expect(() => readDemo('/cards/private-real-id')).toThrow('演示卡片不存在')
})

test('logout clears private data and restores guest browsing', async () => {
  history.replaceState(null, '', '/me')
  let loggedIn = true
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/auth/config') return json({ registration_enabled: true })
    if (path === '/api/auth/me') return loggedIn ? json({ id: 'logout-user', username: 'logoutuser', role: 'member', is_active: true, csrf_token: 'test-token' }) : json({}, 401)
    if (path === '/api/auth/logout') { loggedIn = false; return new Response(null, { status: 204 }) }
    if (path === '/api/me/profile') return json({ ...readDemo<Profile>('/me/profile'), display_name: '退出前的私人资料', bio: '不能保留在游客页面' })
    return json(readDemo(path.slice(4)))
  }))
  render(<App/>)
  await screen.findByRole('heading', { name: '退出前的私人资料' })
  fireEvent.click(screen.getByRole('button', { name: /logoutuser/ }))
  fireEvent.click(await screen.findByRole('button', { name: '退出登录' }))
  await screen.findByText('演示空间 · 只读')
  await screen.findByRole('link', { name: '主动回忆为什么有效？' })
  expect(screen.queryByText('不能保留在游客页面')).toBeNull()
})
