// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useSearchParams } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Identity, type Session } from './lib/workspace'
import { TagFilter, TagSelector } from './components/Selectors'
import { tagQuery } from './lib/tag-filter'
import { useState } from 'react'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
function mount(element: React.ReactNode, route = '/') {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <Identity
        value={{
          session: { id: 'owner', csrf_token: 'csrf' } as Session,
          openLogin: () => {},
          refresh: async () => {},
        }}
      >
        <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>
      </Identity>
    </QueryClientProvider>,
  )
}
function Editor({ initial = [] }: { initial?: string[] }) {
  const [ids, setIds] = useState(initial)
  return (
    <>
      <TagSelector selected={ids} onChange={setIds} allowCreate />
      <output>{ids.join(',')}</output>
    </>
  )
}
test('keyboard selection removal, escaped suggestions and duplicate creation retain selection', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url, options) =>
      options?.method === 'POST'
        ? json({ detail: { message: '已存在', existing_tag: { id: 'ai', name: 'AI' } } }, 409)
        : json({
            items: [
              { id: 'ai', name: 'AI' },
              { id: 'llm', name: 'LLM' },
            ],
          }),
    ),
  )
  mount(<Editor />)
  const input = screen.getByRole('textbox', { name: '搜索标签' })
  await screen.findByRole('button', { name: 'AI' })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('button', { name: '移除 AI' })).toBeTruthy()
  fireEvent.change(input, { target: { value: 'ＡＩ' } })
  fireEvent.click(screen.getByRole('button', { name: '新建标签' }))
  await screen.findByText('已选用同名标签')
  fireEvent.keyDown(input, { key: 'Escape' })
  expect(screen.queryByLabelText('可选标签')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '移除 AI' }))
  expect(screen.getByText('可稍后整理')).toBeTruthy()
})
test('30 selected tags block adding and creation but permit removal', async () => {
  const items = Array.from({ length: 31 }, (_, i) => ({ id: String(i), name: '标签' + i }))
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => json({ items })),
  )
  mount(<Editor initial={items.slice(0, 30).map((t) => t.id)} />)
  expect(await screen.findByRole('button', { name: '标签30' })).toHaveProperty('disabled', true)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '新名字' } })
  expect(screen.getByRole('button', { name: '新建标签' })).toHaveProperty('disabled', true)
  fireEvent.click(screen.getByRole('button', { name: '移除 标签0' }))
  expect(screen.getByRole('button', { name: '新建标签' })).toHaveProperty('disabled', false)
})
function FilterRoute() {
  const [search] = useSearchParams()
  return (
    <>
      <TagFilter />
      <output>{search.toString()}</output>
    </>
  )
}
test('filter URL keeps unrelated state, sorts IDs and resets pagination', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      json({
        items: [
          { id: 'b', name: 'LLM' },
          { id: 'a', name: 'AI' },
        ],
      }),
    ),
  )
  mount(<FilterRoute />, '/?q=hello&type=reference&offset=24&tag_ids=b')
  fireEvent.click(await screen.findByRole('button', { name: 'AI' }))
  await waitFor(() =>
    expect(screen.getByRole('status').textContent).toBe(
      'q=hello&type=reference&tag_ids=a&tag_ids=b&tag_match=all',
    ),
  )
  fireEvent.change(screen.getByLabelText('标签匹配方式'), { target: { value: 'any' } })
  expect(screen.getByRole('status').textContent).toContain('tag_match=any')
  expect(tagQuery(new URLSearchParams('topic=old&tag=other'))).toBe('topic_id=old&tag_id=other')
  fireEvent.click(screen.getByRole('button', { name: '清空标签筛选' }))
  expect(screen.getByRole('status').textContent).toBe('q=hello&type=reference')
})

test('mixed legacy and unified URL conditions reach server validation without dropping filters', () => {
  const query = new URLSearchParams(
    tagQuery(new URLSearchParams('tag_ids=new&topic=old&tag=other')),
  )
  expect(query.getAll('tag_ids')).toEqual(['new'])
  expect(query.get('topic_id')).toBe('old')
  expect(query.get('tag_id')).toBe('other')
})
