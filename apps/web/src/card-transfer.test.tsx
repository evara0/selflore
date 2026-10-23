// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import CardTransfer from './features/profile/CardTransfer'
import { Identity, type Session } from './lib/workspace'

const session = {
  id: 'owner',
  username: 'alice',
  role: 'member',
  is_active: true,
  csrf_token: 'csrf',
} as Session
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
function mount() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Identity value={{ session, openLogin: vi.fn(), refresh: async () => {} }}>
        <CardTransfer />
      </Identity>
    </QueryClientProvider>,
  )
}
function choose(name = 'cards.json') {
  fireEvent.change(screen.getByLabelText('JSON或ZIP文件'), {
    target: { files: [new File(['{}'], name, { type: 'application/json' })] },
  })
}
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('预检错误可定位，换文件清除旧结果，失败时禁止提交', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      json(
        {
          detail: {
            message: '格式无效',
            errors: [{ path: 'cards.0.title', message: '标题必填', card_key: 'card-a' }],
          },
        },
        422,
      ),
    ),
  )
  mount()
  choose()
  expect((screen.getByText('确认导入新卡片') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByText('预检文件'))
  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'card-a · cards.0.title：标题必填',
  )
  choose('corrected.json')
  expect(screen.queryByRole('alert')).toBeNull()
  expect((screen.getByText('确认导入新卡片') as HTMLButtonElement).disabled).toBe(true)
})

test('重试保持批次键、成功阻止重复导入并可开始新批次', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ digest: 'a'.repeat(64), card_count: 6, asset_count: 0 }))
    .mockRejectedValueOnce(new Error('网络断开'))
    .mockResolvedValueOnce(json({ card_count: 6, asset_count: 0 }))
  vi.stubGlobal('fetch', fetcher)
  mount()
  choose()
  fireEvent.click(screen.getByText('预检文件'))
  await screen.findByText(/预检内容：6 张卡片/)
  fireEvent.click(screen.getByText('确认导入新卡片'))
  await screen.findByText('网络断开')
  fireEvent.click(screen.getByText('确认导入新卡片'))
  await screen.findByText('导入成功：6 张卡片，0 张图片。')
  const first = fetcher.mock.calls[1][1].body as FormData
  const retry = fetcher.mock.calls[2][1].body as FormData
  expect(first.get('batch_id')).toBe(retry.get('batch_id'))
  expect((screen.getByText('确认导入新卡片') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByText('开始新批次'))
  expect(screen.queryByText(/已选择/)).toBeNull()
})

test('导出范围和含图提示可见，默认ZIP，JSON失败不显示成功', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(json({ detail: { message: '内容包含图片，请选择ZIP完整导出' } }, 409)),
  )
  mount()
  const help = screen.getByText('格式与说明').closest('details')!
  expect(help.open).toBe(false)
  fireEvent.click(screen.getByText('格式与说明'))
  expect(help.open).toBe(true)
  expect(screen.getByText(/不含合集结构/)).toBeTruthy()
  expect((screen.getByLabelText('导出格式') as HTMLSelectElement).value).toBe('zip')
  fireEvent.change(screen.getByLabelText('导出格式'), { target: { value: 'json' } })
  fireEvent.click(screen.getByText('导出全部卡片'))
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('请选择ZIP'))
  expect(screen.queryByText('完整导出已下载。请妥善保存文件。')).toBeNull()
})
