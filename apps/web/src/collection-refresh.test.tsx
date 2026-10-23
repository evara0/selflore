// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Identity, type Session } from './lib/workspace'
import Collections from './features/collections/Collections'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test.each([false, true])(
  'collection waits for detail refresh before the next write (conflict=%s)',
  async (conflict) => {
    const cards = ['第一张', '第二张'].map((title, index) => ({
      id: `card-${index}`,
      title,
      code: `K-${index}`,
      kind: 'knowledge',
      lifecycle: 'active',
      topics: [],
      tags: [],
    }))
    const writes: number[] = []
    const items: object[] = []
    let released = false
    let releaseDetail: (() => void) | undefined
    const collection = () => ({
      id: 'collection',
      title: '测试合集',
      revision: items.length + 1,
      total_items: items.length,
      lifecycle: 'active',
      cover_color: 'blue',
      cover_style: 'plain',
    })
    const json = (value: unknown, status = 200) =>
      new Response(JSON.stringify(value), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        const path = url.split('?')[0]
        if (init?.method === 'POST') {
          const body = JSON.parse(init.body as string)
          writes.push(body.expected_revision)
          if (conflict && writes.length === 2)
            return json({ detail: '合集已被另一个窗口修改' }, 409)
          const card = cards.find((c) => c.id === body.card_ids[0])!
          items.push({ ...card, item_id: `item-${items.length}`, position: items.length })
          return json(collection())
        }
        if (path === '/api/collections/collection') {
          if (writes.length === 1 && !released)
            return new Promise<Response>((resolve) => {
              releaseDetail = () => {
                released = true
                resolve(json(collection()))
              }
            })
          return json(collection())
        }
        if (path === '/api/collections/collection/items')
          return json({ items: [...items], revision: items.length + 1 })
        if (path === '/api/collections') return json({ items: [collection()], total: 1 })
        if (path === '/api/cards') return json({ items: cards, total: cards.length })
        throw new Error(`Unexpected request: ${url}`)
      }),
    )
    const cache = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
    render(
      <QueryClientProvider client={cache}>
        <Identity
          value={{
            session: { id: 'user', csrf_token: 'token' } as Session,
            openLogin: () => {},
            refresh: async () => {},
          }}
        >
          <MemoryRouter initialEntries={['/collections/collection']}>
            <Routes>
              <Route path="/collections/:id" element={<Collections />} />
            </Routes>
          </MemoryRouter>
        </Identity>
      </QueryClientProvider>,
    )
    const add = await screen.findByRole('button', { name: '＋ 添加卡片' })
    fireEvent.click(add)
    fireEvent.click(await screen.findByRole('button', { name: /第一张/ }))
    await waitFor(() => expect(document.querySelectorAll('.directory-row')).toHaveLength(1))
    await waitFor(() => expect(releaseDetail).toBeTypeOf('function'))
    expect((add as HTMLButtonElement).disabled).toBe(true)
    expect(
      (screen.getByRole('button', { name: '移除 第一张' }) as HTMLButtonElement).disabled,
    ).toBe(true)
    fireEvent.click(add)
    expect(writes).toEqual([1])
    releaseDetail!()
    await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(add)
    fireEvent.click(await screen.findByRole('button', { name: /第二张/ }))
    await waitFor(() => expect(writes).toEqual([1, 2]))
    if (conflict) {
      await screen.findByText('合集已被另一个窗口修改')
      expect(items).toHaveLength(1)
    } else {
      await waitFor(() => expect(document.querySelectorAll('.directory-row')).toHaveLength(2))
    }
    await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false))
    expect(writes).toHaveLength(2)
  },
)
