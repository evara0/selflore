// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { demoId, readDemo } from './lib/demo'

const calls: { path: string; method: string; body?: Record<string, unknown> }[] = []
const session = { id: demoId(900), username: 'importer', role: 'member', csrf_token: 'csrf' }
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const draft = {
  kind: 'memo',
  memo_format: 'checklist',
  title: '论文需求',
  memo_items: [{ text: '安卓阅读' }],
}
let failSave = false,
  failPreview = false
let saved: Record<string, unknown> | undefined

beforeEach(() => {
  history.replaceState(null, '', '/import')
  calls.length = 0
  saved = undefined
  failSave = failPreview = false
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method || 'GET',
        body = init?.body ? JSON.parse(String(init.body)) : undefined
      calls.push({ path, method, body })
      if (path === '/api/auth/me') return json(session)
      if (path === '/api/auth/config') return json({ registration_enabled: true })
      if (path === '/api/cards/import-preview') {
        if (failPreview) return json({ detail: { message: 'kind：请选择有效类别' } }, 422)
        const content = JSON.parse(body.json_text)
        return json({
          form: null,
          body_md: null,
          note_md: null,
          question_md: null,
          answer_md: null,
          attachments: [],
          tag_ids: [],
          memo_items: [],
          memo_columns: ['条目', '字段 2', '字段 3'],
          memo_column_count: 1,
          ...content,
          ...(content.memo_items
            ? {
                memo_items: content.memo_items.map((item: object) => ({
                  id: demoId(950),
                  extra_values: ['', ''],
                  is_completed: false,
                  target_ids: [],
                  ...item,
                })),
              }
            : {}),
        })
      }
      if (path === '/api/cards' && method === 'POST') {
        if (failSave) {
          failSave = false
          return json({ detail: { message: '暂时无法保存' } }, 503)
        }
        saved = { ...body, id: demoId(951), revision: 1, lifecycle: 'active', tags: [], topics: [] }
        return json(saved, 201)
      }
      if (saved && path === '/api/cards/' + saved.id) return json(saved)
      if (path.endsWith('/links')) return json({ incoming: [], outgoing: [] })
      return json(readDemo(path.slice(4)))
    }),
  )
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function prepare(content = draft) {
  await screen.findByRole('heading', { name: 'JSON 导入' }, { timeout: 5000 })
  fireEvent.change(screen.getByRole('textbox', { name: 'JSON 内容' }), {
    target: { value: JSON.stringify(content) },
  })
  fireEvent.click(screen.getByRole('button', { name: '校验并预览' }))
  await screen.findByRole('button', { name: '确认导入' })
}

test('global new route offers import without any category selection and preview writes nothing', async () => {
  history.replaceState(null, '', '/new')
  render(<App />)
  fireEvent.click(await screen.findByRole('link', { name: 'JSON 导入' }, { timeout: 5000 }))
  await prepare()
  expect(location.pathname).toBe('/import')
  const preview = screen.getByRole('region', { name: '导入预览' })
  expect(within(preview).getByRole('heading', { name: '论文需求' })).toBeTruthy()
  expect(within(preview).getByText('安卓阅读')).toBeTruthy()
  expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual([
    '/api/cards/import-preview',
  ])
})

test('editing invalidates preview and server errors retain the original JSON', async () => {
  render(<App />)
  await prepare()
  const input = screen.getByRole('textbox', { name: 'JSON 内容' })
  fireEvent.change(input, { target: { value: '{"title":"没有类别"}' } })
  expect(screen.queryByRole('button', { name: '确认导入' })).toBeNull()
  failPreview = true
  fireEvent.click(screen.getByRole('button', { name: '校验并预览' }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'kind：请选择有效类别')
  expect(input).toHaveProperty('value', '{"title":"没有类别"}')
  expect(calls.some((c) => c.path === '/api/cards' && c.method === 'POST')).toBe(false)
})

test('saving retries exactly the same prepared payload and enters memo detail', async () => {
  render(<App />)
  await prepare()
  fireEvent.click(screen.getByRole('button', { name: '校验并预览' }))
  expect(calls.filter((c) => c.path === '/api/cards/import-preview')).toHaveLength(1)
  failSave = true
  fireEvent.click(screen.getByRole('button', { name: '确认导入' }))
  await screen.findByText('暂时无法保存')
  expect(screen.getByRole('textbox', { name: 'JSON 内容' })).toHaveProperty(
    'value',
    JSON.stringify(draft),
  )
  fireEvent.click(screen.getByRole('button', { name: '确认导入' }))
  await waitFor(() => expect(location.pathname).toBe('/memos/' + demoId(951)))
  const writes = calls.filter((c) => c.path === '/api/cards' && c.method === 'POST')
  expect(writes).toHaveLength(2)
  expect(writes[0].body).toEqual(writes[1].body)
  expect(writes[0].body?.client_request_id).toBeTruthy()
})

test('leaving a draft prompts and cancel retains input while empty import leaves freely', async () => {
  const confirm = vi.fn(() => false)
  vi.stubGlobal('confirm', confirm)
  render(<App />)
  await screen.findByRole('heading', { name: 'JSON 导入' }, { timeout: 5000 })
  fireEvent.change(screen.getByRole('textbox', { name: 'JSON 内容' }), { target: { value: '{}' } })
  fireEvent.click(screen.getByRole('link', { name: '手动新建' }))
  await waitFor(() => expect(confirm).toHaveBeenCalled())
  expect(location.pathname).toBe('/import')
  fireEvent.change(screen.getByRole('textbox', { name: 'JSON 内容' }), { target: { value: '' } })
  fireEvent.click(screen.getByRole('link', { name: '手动新建' }))
  await waitFor(() => expect(location.pathname).toBe('/new'))
})
