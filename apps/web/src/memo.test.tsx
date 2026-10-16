// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { readDemo, demoId } from './lib/demo'
import { legacyList, preferredType, rememberType } from './lib/card-navigation'
import type { Card } from './lib/workspace'

const session = { id: 'memo-user', username: 'alice', role: 'member', csrf_token: 'csrf' }
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const calls: { path: string; method: string; body?: Record<string, unknown> }[] = []
let current: Card,
  failWrite = false,
  saved: Card | undefined
function mock(guest = false) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method || 'GET',
        body = init?.body ? JSON.parse(String(init.body)) : undefined
      calls.push({ path, method, body })
      if (path === '/api/auth/me') return guest ? json({}, 401) : json(session)
      if (path === '/api/auth/config') return json({ registration_enabled: true })
      if (method !== 'GET') {
        if (failWrite) return json({ detail: { message: '修订冲突，请重新读取' } }, 409)
        if (path === '/api/cards') {
          saved = {
            ...current,
            ...body,
            id: demoId(80),
            kind: 'memo',
            form: null,
            title: String(body.title),
            revision: 1,
          } as Card
          return json(saved, 201)
        }
        current = {
          ...current,
          revision: current.revision + 1,
          memo_items: current.memo_items?.map((item, i) =>
            i === 1 ? { ...item, is_completed: true } : item,
          ),
        }
        return json(current)
      }
      if (saved && path === '/api/cards/' + saved.id) return json(saved)
      if (path === '/api/cards/' + current.id) return json(current)
      return json(readDemo(path.slice(4)))
    }),
  )
}
beforeEach(() => {
  localStorage.clear()
  calls.length = 0
  failWrite = false
  saved = undefined
  current = readDemo<Card>('/cards/' + demoId(12))
  history.replaceState(null, '', '/memos')
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  localStorage.clear()
})

test('four navigation destinations retain the separate mobile creation action', async () => {
  mock()
  render(<App />)
  await screen.findByRole('heading', { name: '备忘' })
  const desktop = screen.getByRole('navigation', { name: '主导航' })
  expect(
    within(desktop)
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual(['卡片', '备忘', '合集', '我的'])
  expect(
    within(screen.getByRole('navigation', { name: '移动端导航' }))
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual(['卡片', '备忘', '＋新建', '合集', '我的'])
  expect(screen.queryByRole('button', { name: '开始复习' })).toBeNull()
})

test('guest pending items derive from sample checklist and completion only opens login', async () => {
  mock(true)
  history.replaceState(null, '', '/memos?view=open')
  render(<App />)
  const checkbox = await screen.findByRole('checkbox')
  fireEvent.click(checkbox)
  await waitFor(() => expect(screen.getByRole('dialog').hasAttribute('open')).toBe(true))
  expect((checkbox as HTMLInputElement).checked).toBe(false)
  expect(calls.every((call) => call.path.startsWith('/api/auth/'))).toBe(true)
})

test('title-only memo saves with no required source or classification', async () => {
  mock()
  history.replaceState(null, '', '/new?kind=memo')
  render(<App />)
  fireEvent.change(await screen.findByLabelText('标题'), { target: { value: '明天查一下这件事' } })
  fireEvent.click(screen.getByRole('button', { name: '保存备忘' }))
  await screen.findByRole('heading', { name: '明天查一下这件事' })
  const write = calls.find((call) => call.path === '/api/cards' && call.method === 'POST')!
  expect(write.body).toMatchObject({
    kind: 'memo',
    memo_format: 'note',
    body_md: null,
    memo_items: [],
    tag_ids: [],
    source_url: null,
  })
  expect(location.pathname).toBe('/memos/' + demoId(80))
})

test('checklist editor preserves item identity while adding sorting and associating', async () => {
  mock()
  history.replaceState(null, '', '/new?kind=memo&memo_format=checklist')
  render(<App />)
  fireEvent.change(await screen.findByLabelText('标题'), { target: { value: '待学清单' } })
  fireEvent.change(screen.getByLabelText('条目 1'), { target: { value: '第一项' } })
  expect(screen.getByRole('button', { name: '删除条目' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: '＋ 添加条目' }))
  fireEvent.change(screen.getByLabelText('条目 2'), { target: { value: '第二项' } })
  fireEvent.click(screen.getByRole('button', { name: '上移条目 2' }))
  expect(screen.getByLabelText('条目 1')).toHaveProperty('value', '第二项')
  failWrite = true
  fireEvent.click(screen.getByRole('button', { name: '保存备忘' }))
  await screen.findByText('修订冲突，请重新读取')
  expect(screen.getByLabelText('条目 1')).toHaveProperty('value', '第二项')
  fireEvent.click(screen.getByRole('button', { name: '保存备忘' }))
  await waitFor(() =>
    expect(calls.filter((c) => c.path === '/api/cards' && c.method === 'POST')).toHaveLength(2),
  )
  const writes = calls.filter((c) => c.path === '/api/cards' && c.method === 'POST')
  expect(writes[0].body?.client_request_id).toBe(writes[1].body?.client_request_id)
  expect(writes[0].body?.memo_items).toEqual(writes[1].body?.memo_items)
})

test('failed completion preserves the checkbox and does not blindly retry or flip', async () => {
  mock()
  failWrite = true
  history.replaceState(null, '', '/memos/' + current.id)
  render(<App />)
  const boxes = await screen.findAllByRole('checkbox')
  fireEvent.click(boxes[1])
  await screen.findByRole('alert')
  expect((boxes[1] as HTMLInputElement).checked).toBe(false)
  const writes = calls.filter((c) => c.method === 'PATCH')
  expect(writes).toHaveLength(1)
  expect(writes[0].body).toMatchObject({ expected_revision: 1, is_completed: true })
})

test('card list type memory is separated by account and explicit URLs win', async () => {
  rememberType('alice', 'opinion')
  rememberType('bob', 'reference')
  expect(preferredType('alice')).toBe('opinion')
  expect(preferredType('bob')).toBe('reference')
  expect(preferredType('guest')).toBe('all')
  rememberType(session.id, 'opinion')
  mock()
  history.replaceState(null, '', '/cards?type=reference')
  render(<App />)
  await screen.findByRole('link', { name: '一周借阅记录' })
  expect(screen.getByRole('button', { name: '资料' }).classList.contains('selected')).toBe(true)
  expect(calls.some((c) => c.path.includes('kind=reference'))).toBe(true)
})

test('legacy lists preserve query and selected opinion identity', () => {
  const migrated = new URL(
    legacyList('?card=abc&q=中文&topic=theme&state=inbox&offset=12', true),
    'https://local.test',
  )
  expect(migrated.pathname).toBe('/cards')
  expect(migrated.searchParams.get('type')).toBe('opinion')
  expect(migrated.searchParams.get('card')).toBe('abc')
  expect(migrated.searchParams.get('q')).toBe('中文')
  expect(migrated.searchParams.get('offset')).toBe('12')
  expect(
    new URL(legacyList('?type=reference&tag=a'), 'https://local.test').searchParams.get('type'),
  ).toBe('reference')
})

test('checklist editor enforces 200 items and allows deleting then adding', async () => {
  current.memo_items = Array.from({ length: 200 }, (_, index) => ({
    id: crypto.randomUUID(),
    text: '事项 ' + index,
    is_completed: false,
    target_ids: [],
  }))
  mock()
  history.replaceState(null, '', '/memos/' + current.id + '/edit')
  render(<App />)
  const add = await screen.findByRole('button', { name: '＋ 添加条目' })
  expect(add).toHaveProperty('disabled', true)
  fireEvent.click(screen.getAllByRole('button', { name: '删除条目' })[199])
  expect(add).toHaveProperty('disabled', false)
  fireEvent.click(add)
  expect(add).toHaveProperty('disabled', true)
  expect(screen.getAllByRole('textbox', { name: /^条目 / })).toHaveLength(200)
}, 20000)

test('finishing the last item of a final page returns to a valid server page', async () => {
  mock()
  const originalFetch = globalThis.fetch
  let completed = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') {
        completed = true
        return json(current)
      }
      if (path.startsWith('/api/memo-items?')) {
        const offset = Number(new URL(path, 'https://local.test').searchParams.get('offset'))
        return json({
          items:
            completed && offset === 12
              ? []
              : [
                  {
                    ...current.memo_items![1],
                    memo_card_id: current.id,
                    memo_title: current.title,
                    revision: 1,
                  },
                ],
          total: completed ? 12 : 13,
          limit: 12,
          offset,
        })
      }
      return originalFetch(path, init)
    }),
  )
  history.replaceState(null, '', '/memos?view=open&offset=12')
  render(<App />)
  fireEvent.click(await screen.findByRole('checkbox'))
  await waitFor(() => expect(new URLSearchParams(location.search).get('offset')).toBe('0'))
  expect(await screen.findByText('12 项未完成事项')).toBeTruthy()
})

test('blocked local storage keeps browsing preferences optional', () => {
  const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  try {
    expect(preferredType('alice')).toBe('all')
    expect(() => rememberType('alice', 'opinion')).not.toThrow()
  } finally {
    get.mockRestore()
    set.mockRestore()
  }
})
